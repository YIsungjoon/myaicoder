# Design: model-management

**Feature**: model-management
**날짜**: 2026-03-14
**Phase**: Design
**Level**: Enterprise
**Plan Reference**: `docs/pdca/01-plan/features/model-management.plan.md`

---

## 1. 설계 개요

환경별 이중 전략으로 모델 관리 시스템을 구축한다.

- **prod (DGX Spark, 128GB)**: 3개 모델 Always-on, Gateway 라우팅만으로 즉시 전환
- **dev (Desktop, 24GB VRAM)**: 1개 모델 로드, CLI `model switch`로 stop → start 전환

### 변경 범위

| 서비스 | 변경 내용 |
|--------|----------|
| `services/myaicoder` | ModelManager, VLLMProcessManager, CLI `model` 서브커맨드, models config |
| `services/gateway` | ModelRouter 동적 갱신 (dev 환경 switch 반영) |
| 프로젝트 루트 | `models.yaml` config 파일 (prod/dev 프로필) |

## 2. 디렉토리 구조

### 2.1 새로 추가되는 파일

```
services/myaicoder/src/myaicoder/
├── models/                          # 신규 모듈
│   ├── __init__.py
│   ├── config.py                    # ModelsConfig — YAML 로드, 환경별 설정
│   ├── scanner.py                   # ModelScanner — GGUF 파일 스캔, 메타데이터
│   ├── process.py                   # VLLMProcessManager — vLLM 프로세스 관리
│   └── manager.py                   # ModelManager — 오케스트레이션 (facade)
├── cli.py                           # 기존 파일 수정 — model 서브커맨드 추가

services/myaicoder/tests/
├── test_models/                     # 신규 테스트
│   ├── test_config.py
│   ├── test_scanner.py
│   ├── test_process.py
│   └── test_manager.py

프로젝트 루트 (또는 ~/.config/myaicoder/):
├── models.yaml                      # 모델 프로필 설정
```

### 2.2 기존 파일 수정

| 파일 | 수정 내용 |
|------|----------|
| `services/myaicoder/src/myaicoder/cli.py` | `model` 그룹 커맨드 추가 (list, switch, status, launch) |
| `services/myaicoder/src/myaicoder/core/config.py` | `ModelsConfig` 참조 추가 (선택적) |
| `services/gateway/app/router.py` | `update_routes()` 메서드 추가 (dev switch 연동, P1) |

## 3. 모듈 상세 설계

### 3.1 ModelsConfig (`models/config.py`)

모델 설정 YAML을 로드하고 환경별 설정을 제공한다.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class VLLMArgs:
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 32768
    extra_args: list[str] = field(default_factory=list)


@dataclass
class ModelDefaults:
    temperature: float = 0.0
    max_tokens: int = 8192


@dataclass
class ModelProfile:
    name: str
    file: str
    description: str = ""
    port: int = 8001
    always_on: bool = False
    vllm_args: VLLMArgs = field(default_factory=VLLMArgs)
    defaults: ModelDefaults = field(default_factory=ModelDefaults)


@dataclass
class ModelsConfig:
    environment: str = "dev"          # "prod" | "dev"
    models_dir: str = "~/models"
    default_model: str = ""
    port: int = 8001                  # dev 기본 포트
    instances: list[ModelProfile] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path | None = None) -> ModelsConfig:
        """Load models config. Search: explicit → ./models.yaml → ~/.config/myaicoder/models.yaml"""
        search = []
        if path:
            search.append(Path(path))
        search.extend([
            Path.cwd() / "models.yaml",
            Path.home() / ".config" / "myaicoder" / "models.yaml",
        ])

        for p in search:
            if p.exists():
                return cls._from_yaml(p)
        return cls()

    @classmethod
    def _from_yaml(cls, path: Path) -> ModelsConfig:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        # ... 파싱 로직 ...

    def is_prod(self) -> bool:
        return self.environment == "prod"

    def get_profile(self, name: str) -> ModelProfile | None:
        return next((m for m in self.instances if m.name == name), None)

    def get_default_profile(self) -> ModelProfile | None:
        if self.default_model:
            return self.get_profile(self.default_model)
        return self.instances[0] if self.instances else None
```

### 3.2 ModelScanner (`models/scanner.py`)

모델 디렉토리를 스캔하여 사용 가능한 GGUF 파일 목록을 반환한다.

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelFile:
    name: str          # 프로필 이름 (config 매칭) 또는 파일명
    path: Path         # 절대 경로
    size_bytes: int    # 파일 크기
    registered: bool   # config에 등록된 모델인지

    @property
    def size_human(self) -> str:
        """Human-readable size (e.g., '16.2GB')"""
        gb = self.size_bytes / (1024 ** 3)
        return f"{gb:.1f}GB"


class ModelScanner:
    """Scans models directory for GGUF files."""

    def __init__(self, models_dir: str | Path, config: ModelsConfig):
        self._dir = Path(models_dir).expanduser()
        self._config = config

    def scan(self) -> list[ModelFile]:
        """Scan for *.gguf files and match against config profiles."""
        if not self._dir.exists():
            return []

        results = []
        config_files = {p.file: p.name for p in self._config.instances}

        for path in sorted(self._dir.glob("*.gguf")):
            profile_name = config_files.get(path.name, path.stem)
            registered = path.name in config_files
            results.append(ModelFile(
                name=profile_name,
                path=path,
                size_bytes=path.stat().st_size,
                registered=registered,
            ))
        return results
```

### 3.3 VLLMProcessManager (`models/process.py`)

vLLM 서버 프로세스의 생명주기를 관리한다.

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import httpx


class ProcessState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class VLLMInstance:
    model_name: str
    model_path: Path
    port: int
    state: ProcessState = ProcessState.STOPPED
    process: asyncio.subprocess.Process | None = None
    pid: int | None = None


class VLLMProcessManager:
    """Manages vLLM server processes."""

    def __init__(self, vllm_command: str = "vllm"):
        self._instances: dict[int, VLLMInstance] = {}  # port → instance
        self._vllm_cmd = vllm_command

    # ── Lifecycle ──

    async def start(
        self,
        model_path: Path,
        model_name: str,
        port: int,
        vllm_args: VLLMArgs | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> VLLMInstance:
        """Start a vLLM process on the given port."""
        instance = VLLMInstance(
            model_name=model_name,
            model_path=model_path,
            port=port,
            state=ProcessState.STARTING,
        )
        self._instances[port] = instance

        if on_status:
            on_status(f"Loading {model_name} on :{port}...")

        cmd = self._build_command(model_path, port, vllm_args)
        instance.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        instance.pid = instance.process.pid

        # Wait for health check
        ready = await self._wait_for_health(port, timeout=120)
        if ready:
            instance.state = ProcessState.READY
            if on_status:
                on_status(f"{model_name} ready on :{port}")
        else:
            instance.state = ProcessState.ERROR
            await self._kill(instance)
            raise RuntimeError(f"vLLM failed to start: {model_name} on :{port}")

        return instance

    async def stop(self, port: int, graceful: bool = True) -> None:
        """Stop vLLM process on port. Graceful = SIGTERM + wait, else SIGKILL."""
        instance = self._instances.get(port)
        if not instance or not instance.process:
            return

        instance.state = ProcessState.STOPPING

        if graceful:
            instance.process.terminate()
            try:
                await asyncio.wait_for(instance.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                await self._kill(instance)
        else:
            await self._kill(instance)

        instance.state = ProcessState.STOPPED
        instance.process = None
        instance.pid = None

    async def start_all(
        self,
        profiles: list[ModelProfile],
        models_dir: Path,
        on_status: Callable[[str], None] | None = None,
    ) -> list[VLLMInstance]:
        """Start multiple vLLM instances (prod mode). Sequential to avoid memory spike."""
        results = []
        for profile in profiles:
            model_path = models_dir / profile.file
            inst = await self.start(
                model_path=model_path,
                model_name=profile.name,
                port=profile.port,
                vllm_args=profile.vllm_args,
                on_status=on_status,
            )
            results.append(inst)
        return results

    # ── Health Check ──

    async def health_check(self, port: int) -> bool:
        """Check if vLLM on port is healthy."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"http://localhost:{port}/health")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def get_instance(self, port: int) -> VLLMInstance | None:
        return self._instances.get(port)

    def get_running(self) -> list[VLLMInstance]:
        return [i for i in self._instances.values() if i.state == ProcessState.READY]

    # ── Internal ──

    def _build_command(
        self, model_path: Path, port: int, args: VLLMArgs | None
    ) -> list[str]:
        cmd = [
            self._vllm_cmd, "serve", str(model_path),
            "--host", "0.0.0.0",
            "--port", str(port),
        ]
        if args:
            cmd.extend(["--gpu-memory-utilization", str(args.gpu_memory_utilization)])
            cmd.extend(["--max-model-len", str(args.max_model_len)])
            cmd.extend(args.extra_args)
        return cmd

    async def _wait_for_health(self, port: int, timeout: int = 120) -> bool:
        """Poll /health until ready or timeout.
        Fail-fast: 프로세스가 이미 죽었으면 즉시 실패 (dead process 대기 방지)."""
        instance = self._instances.get(port)
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            # Dead process detection: returncode가 None이 아니면 이미 종료됨
            if instance and instance.process and instance.process.returncode is not None:
                stderr = ""
                if instance.process.stderr:
                    stderr = (await instance.process.stderr.read()).decode(errors="replace")
                raise RuntimeError(
                    f"vLLM process exited immediately (code={instance.process.returncode}). "
                    f"Likely cause: VRAM OOM or invalid model.\n{stderr[:500]}"
                )
            if await self.health_check(port):
                return True
            await asyncio.sleep(2)
        return False

    async def _kill(self, instance: VLLMInstance) -> None:
        if instance.process:
            instance.process.kill()
            await instance.process.wait()

    # ── Signal Safety (Zombie Process Prevention) ──

    def install_signal_handlers(self) -> None:
        """Register signal handlers to kill all managed vLLM processes on exit.
        Prevents zombie/orphan processes when CLI is Ctrl+C'd during switch."""
        import signal

        def _cleanup(signum, frame):
            """Synchronous cleanup — kill all managed processes."""
            for instance in self._instances.values():
                if instance.process and instance.process.returncode is None:
                    instance.process.kill()
            # Re-raise for default behavior
            signal.signal(signum, signal.SIG_DFL)
            raise SystemExit(128 + signum)

        signal.signal(signal.SIGINT, _cleanup)
        signal.signal(signal.SIGTERM, _cleanup)

    def uninstall_signal_handlers(self) -> None:
        """Restore default signal handlers after operation completes."""
        import signal
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
```

### 3.4 ModelManager (`models/manager.py`)

모든 모델 관련 작업의 Facade.

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ModelStatus(str, Enum):
    LOADED = "loaded"
    AVAILABLE = "available"
    NOT_FOUND = "not_found"


@dataclass
class ModelInfo:
    name: str
    description: str
    file: str
    size_human: str
    status: ModelStatus
    port: int | None = None


class ModelManager:
    """Facade for model management operations."""

    def __init__(
        self,
        config: ModelsConfig,
        process_manager: VLLMProcessManager,
        scanner: ModelScanner,
    ):
        self._config = config
        self._pm = process_manager
        self._scanner = scanner
        self._models_dir = Path(config.models_dir).expanduser()

    # ── List ──

    def list_models(self) -> list[ModelInfo]:
        """List all models with their current status."""
        files = {mf.name: mf for mf in self._scanner.scan()}
        running = {i.model_name: i for i in self._pm.get_running()}
        result = []

        for profile in self._config.instances:
            mf = files.get(profile.name)
            inst = running.get(profile.name)

            status = ModelStatus.NOT_FOUND
            if mf:
                status = ModelStatus.LOADED if inst else ModelStatus.AVAILABLE

            result.append(ModelInfo(
                name=profile.name,
                description=profile.description,
                file=profile.file,
                size_human=mf.size_human if mf else "?",
                status=status,
                port=inst.port if inst else None,
            ))
        return result

    # ── Switch (dev only) ──

    async def switch_model(
        self,
        target_name: str,
        on_status: Callable[[str], None] | None = None,
    ) -> ModelInfo:
        """Switch to a different model. Dev environment only.

        Safety features:
        - Signal handler: Ctrl+C 시 자식 vLLM 프로세스도 함께 kill (좀비 방지)
        - Dead process detection: vLLM이 즉시 크래시하면 120초 대기 없이 즉시 실패
        - Rollback: 새 모델 로드 실패 시 이전 모델 자동 복원
        - Gateway notify: switch 성공 시 Gateway에 HTTP로 라우팅 갱신 통지
        """
        if self._config.is_prod():
            raise RuntimeError(
                "모든 모델이 이미 로드되어 있습니다 (prod 환경). "
                "Gateway에서 model 파라미터로 선택하세요."
            )

        profile = self._config.get_profile(target_name)
        if not profile:
            raise ValueError(f"Unknown model: {target_name}")

        model_path = self._models_dir / profile.file
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        port = self._config.port  # dev는 단일 포트
        current = self._pm.get_instance(port)
        previous_name = current.model_name if current and current.state.value == "ready" else None

        # Signal handler 설치 — Ctrl+C 시 자식 vLLM도 정리
        self._pm.install_signal_handlers()

        try:
            # 1. Stop current
            if current and current.state.value == "ready":
                if on_status:
                    on_status(f"Stopping {current.model_name}...")
                await self._pm.stop(port, graceful=True)

            # 2. Start target
            try:
                vllm_args = profile.vllm_args
                await self._pm.start(
                    model_path=model_path,
                    model_name=target_name,
                    port=port,
                    vllm_args=vllm_args,
                    on_status=on_status,
                )
            except RuntimeError:
                # Rollback: restart previous model
                if previous_name and on_status:
                    on_status(f"Failed. Rolling back to {previous_name}...")
                if previous_name:
                    prev_profile = self._config.get_profile(previous_name)
                    if prev_profile:
                        prev_path = self._models_dir / prev_profile.file
                        await self._pm.start(
                            model_path=prev_path,
                            model_name=previous_name,
                            port=port,
                            vllm_args=prev_profile.vllm_args,
                            on_status=on_status,
                        )
                raise

            # 3. Gateway에 라우팅 갱신 통지 (best-effort)
            await self._notify_gateway(target_name, port)

        finally:
            # Signal handler 복원
            self._pm.uninstall_signal_handlers()

        return ModelInfo(
            name=target_name,
            description=profile.description,
            file=profile.file,
            size_human="",
            status=ModelStatus.LOADED,
            port=port,
        )

    # ── Status ──

    def get_status(self) -> dict:
        """Get current environment and model status summary."""
        running = self._pm.get_running()
        return {
            "environment": self._config.environment,
            "models_dir": str(self._models_dir),
            "loaded_models": len(running),
            "total_models": len(self._config.instances),
            "models": [
                {
                    "name": i.model_name,
                    "port": i.port,
                    "state": i.state.value,
                }
                for i in running
            ],
        }

    # ── Launch ──

    async def launch(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> list[VLLMInstance]:
        """Launch vLLM processes based on environment config."""
        if self._config.is_prod():
            # prod: start all always_on instances
            profiles = [p for p in self._config.instances if p.always_on]
            return await self._pm.start_all(
                profiles=profiles,
                models_dir=self._models_dir,
                on_status=on_status,
            )
        else:
            # dev: start default model only
            default = self._config.get_default_profile()
            if not default:
                raise RuntimeError("No default model configured")
            model_path = self._models_dir / default.file
            inst = await self._pm.start(
                model_path=model_path,
                model_name=default.name,
                port=self._config.port,
                vllm_args=default.vllm_args,
                on_status=on_status,
            )
            return [inst]
```

## 4. CLI 설계

### 4.1 `model` 서브커맨드 그룹 (`cli.py` 수정)

기존 `main` 그룹에 `model` 서브커맨드 그룹을 추가한다.

```python
@main.group()
@click.pass_context
def model(ctx):
    """Model management commands."""
    pass


@model.command("list")
def model_list():
    """List available models and their status."""
    config = ModelsConfig.load()
    pm = VLLMProcessManager()
    scanner = ModelScanner(config.models_dir, config)
    mgr = ModelManager(config, pm, scanner)

    models = mgr.list_models()
    env_label = f"{config.environment} ({'DGX Spark, 128GB' if config.is_prod() else 'Desktop, 24GB VRAM'})"
    click.echo(f"  ENV: {env_label}\n")

    # Table header
    if config.is_prod():
        click.echo(f"  {'NAME':<20} {'SIZE':<8} {'PORT':<6} {'STATUS':<12} DESCRIPTION")
    else:
        click.echo(f"  {'NAME':<20} {'SIZE':<8} {'STATUS':<12} DESCRIPTION")

    for m in models:
        status_str = f"loaded ●" if m.status == ModelStatus.LOADED else m.status.value
        if config.is_prod():
            port_str = str(m.port) if m.port else "-"
            click.echo(f"  {m.name:<20} {m.size_human:<8} {port_str:<6} {status_str:<12} {m.description}")
        else:
            click.echo(f"  {m.name:<20} {m.size_human:<8} {status_str:<12} {m.description}")


@model.command("switch")
@click.argument("name")
def model_switch(name):
    """Switch to a different model (dev environment only)."""
    import asyncio

    config = ModelsConfig.load()
    pm = VLLMProcessManager()
    scanner = ModelScanner(config.models_dir, config)
    mgr = ModelManager(config, pm, scanner)

    def on_status(msg):
        click.echo(f"  ⏳ {msg}")

    try:
        result = asyncio.run(mgr.switch_model(name, on_status=on_status))
        click.echo(f"  ✓ Model switched to {result.name}")
    except RuntimeError as e:
        click.echo(f"  ✗ {e}", err=True)
    except FileNotFoundError as e:
        click.echo(f"  ✗ {e}", err=True)


@model.command("status")
def model_status():
    """Show current model and environment status."""
    config = ModelsConfig.load()
    pm = VLLMProcessManager()
    scanner = ModelScanner(config.models_dir, config)
    mgr = ModelManager(config, pm, scanner)

    status = mgr.get_status()
    click.echo(f"  Environment: {status['environment']}")
    click.echo(f"  Models dir:  {status['models_dir']}")
    click.echo(f"  Loaded:      {status['loaded_models']}/{status['total_models']}")
    for m in status["models"]:
        click.echo(f"    {m['name']} (:{m['port']}) — {m['state']}")


@model.command("launch")
@click.option("--env", type=click.Choice(["prod", "dev"]), default=None, help="Environment override")
def model_launch(env):
    """Launch vLLM processes for the current environment."""
    import asyncio

    config = ModelsConfig.load()
    if env:
        config.environment = env

    pm = VLLMProcessManager()
    scanner = ModelScanner(config.models_dir, config)
    mgr = ModelManager(config, pm, scanner)

    def on_status(msg):
        click.echo(f"  ⏳ {msg}")

    try:
        instances = asyncio.run(mgr.launch(on_status=on_status))
        click.echo(f"\n  ✓ {len(instances)} model(s) launched")
    except Exception as e:
        click.echo(f"  ✗ Launch failed: {e}", err=True)
```

## 5. 환경별 Config 파일 (`models.yaml`)

### 5.1 Config 로드 우선순위

1. CLI `--config` 플래그로 지정된 경로
2. `./models.yaml` (프로젝트 디렉토리)
3. `~/.config/myaicoder/models.yaml` (사용자 디렉토리)

### 5.2 prod.yaml 예시

```yaml
environment: prod
models_dir: "~/models"

instances:
  - name: "qwen3.5-27b"
    file: "Qwen3.5-27B-Q4_K_M.gguf"
    port: 8001
    always_on: true
    description: "Qwen 3.5 27B — 고품질 범용 모델"
    vllm_args:
      gpu_memory_utilization: 0.3
      max_model_len: 32768
    defaults:
      temperature: 0.0
      max_tokens: 8192

  - name: "qwen3.5-9b"
    file: "Qwen3.5-9B-Q4_K_M.gguf"
    port: 8002
    always_on: true
    description: "Qwen 3.5 9B — 빠른 응답 모델"
    vllm_args:
      gpu_memory_utilization: 0.1
      max_model_len: 32768
    defaults:
      temperature: 0.0
      max_tokens: 8192

  - name: "qwen3-coder-30b"
    file: "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    port: 8003
    always_on: true
    description: "Qwen 3 Coder 30B — 코딩 특화 모델"
    vllm_args:
      gpu_memory_utilization: 0.35
      max_model_len: 16384
    defaults:
      temperature: 0.0
      max_tokens: 8192
```

### 5.3 dev.yaml 예시

```yaml
environment: dev
models_dir: "~/models"
default_model: "qwen3.5-9b"
port: 8001

instances:
  - name: "qwen3.5-27b"
    file: "Qwen3.5-27B-Q4_K_M.gguf"
    description: "Qwen 3.5 27B — 고품질 범용 모델"
    vllm_args:
      gpu_memory_utilization: 0.9
      max_model_len: 32768

  - name: "qwen3.5-9b"
    file: "Qwen3.5-9B-Q4_K_M.gguf"
    description: "Qwen 3.5 9B — 빠른 응답 모델"
    vllm_args:
      gpu_memory_utilization: 0.5
      max_model_len: 32768

  - name: "qwen3-coder-30b"
    file: "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    description: "Qwen 3 Coder 30B — 코딩 특화 모델"
    vllm_args:
      gpu_memory_utilization: 0.95
      max_model_len: 16384
```

## 6. 시퀀스 다이어그램

### 6.1 prod: 사용자 요청 (즉시 라우팅)

```
User → Gateway → ModelRouter.resolve("qwen3-coder-30b")
                          │
                          ▼
                   vLLM :8003 (Always-on)
                          │
                          ▼
                   Response → User
```

전환 비용: 0초. Gateway가 model 파라미터로 즉시 라우팅.

### 6.2 dev: model switch

```
User: myaicoder model switch qwen3-coder-30b
  │
  ▼
ModelManager.switch_model("qwen3-coder-30b")
  │
  ├─ 1. VLLMProcessManager.stop(:8001, graceful=True)
  │     └─ SIGTERM → wait 10s → (SIGKILL if needed)
  │
  ├─ 2. VLLMProcessManager.start(qwen3-coder-30b, :8001)
  │     ├─ subprocess: vllm serve ... --port 8001
  │     └─ _wait_for_health(:8001, timeout=120)
  │         └─ poll GET /health every 2s
  │
  └─ 3. Success → ModelInfo(status=LOADED)
     │
     └─ (Failure → rollback: restart previous model)
```

### 6.3 dev: switch 실패 → 롤백

```
ModelManager.switch_model("qwen3.5-27b")
  │
  ├─ 1. stop(qwen3.5-9b) ✓
  ├─ 2. start(qwen3.5-27b) ✗ (OOM / timeout)
  │
  └─ 3. Rollback:
       ├─ start(qwen3.5-9b)  ← 이전 모델 복원
       └─ raise RuntimeError
```

## 7. Gateway 연동 (P1)

### 7.1 프로세스 분리 문제와 해결

**문제**: CLI(`myaicoder model switch`)는 일회성 프로세스이고, Gateway는 별도 상주 프로세스다.
두 프로세스는 메모리를 공유하지 않으므로, CLI에서 Gateway의 Python 객체를 직접 호출할 수 없다.

**해결**: Gateway에 내부 관리 API를 추가하고, CLI가 HTTP로 통신한다.

```
CLI (model switch 성공)
  │
  └─ POST http://localhost:8080/internal/routes/reload
       Body: {"current_model": "qwen3-coder-30b", "port": 8001}
       Header: X-Internal-Token: <internal_secret>
  │
  ▼
Gateway
  └─ ModelRouter.reload(model_name, upstream)
       └─ _default_upstream 갱신
```

#### Gateway 내부 API 추가 (`gateway/app/main.py`)

```python
@app.post("/internal/routes/reload")
async def reload_routes(
    request: Request,
    body: dict,
    internal_token: str = Header(alias="X-Internal-Token"),
):
    """Reload model routing after dev switch. Internal use only."""
    expected = app.state.config.auth.internal_token
    if not expected or internal_token != expected:
        raise HTTPException(403, "Invalid internal token")

    model_name = body["current_model"]
    port = body["port"]
    upstream = f"http://localhost:{port}/v1"
    app.state.router.reload(model_name, upstream)
    return {"status": "ok", "current_model": model_name}
```

#### ModelRouter 확장 (`gateway/app/router.py`)

```python
class ModelRouter:
    # ... 기존 코드 ...

    def reload(self, model_name: str, upstream: str) -> None:
        """Reload routing for dev environment switch.
        All routes point to the same upstream after switch."""
        self._default_upstream = upstream
        for name in self._routes:
            self._routes[name] = upstream
        logger.info("routes_reloaded", current_model=model_name, upstream=upstream)
```

#### CLI에서 Gateway 통지 (`models/manager.py`)

```python
async def _notify_gateway(self, model_name: str, port: int) -> None:
    """Notify gateway of model switch (best-effort, non-blocking)."""
    gateway_url = self._config.gateway_url  # e.g., "http://localhost:8080"
    if not gateway_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{gateway_url}/internal/routes/reload",
                json={"current_model": model_name, "port": port},
                headers={"X-Internal-Token": self._config.internal_token},
            )
    except httpx.ConnectError:
        pass  # Gateway가 안 떠있으면 무시 (CLI 단독 사용 가능)
```

### 7.2 prod 환경

변경 불필요. 기존 `ModelRouter`가 model 이름 → 포트 매핑을 정확히 수행.

## 8. 테스트 전략

### 8.1 단위 테스트

| 테스트 파일 | 대상 | 주요 케이스 |
|------------|------|-----------|
| `test_config.py` | ModelsConfig | YAML 로드, 환경 감지, 프로필 조회, 기본값 |
| `test_scanner.py` | ModelScanner | GGUF 스캔, 크기 계산, config 매칭, 빈 디렉토리 |
| `test_process.py` | VLLMProcessManager | 커맨드 빌드, 상태 전이, health check mock, dead process fail-fast, signal handler |
| `test_manager.py` | ModelManager | list, switch 워크플로, 롤백, prod 거부, gateway 통지, 좀비 방지 |

### 8.2 테스트 방침

- vLLM 프로세스 실행은 **mock** (subprocess, httpx)
- `ModelScanner`는 **tmp_path fixture**로 실제 파일 생성
- `ModelsConfig`는 **임시 YAML** 작성 후 로드 검증
- 실제 vLLM 연동 테스트는 skip (CI에서 GPU 없음)

## 9. 구현 순서

| 순서 | 작업 | 파일 | 의존 |
|------|------|------|------|
| 1 | ModelsConfig YAML 로드 | `models/config.py` + `test_config.py` | 없음 |
| 2 | ModelScanner GGUF 스캔 | `models/scanner.py` + `test_scanner.py` | 1 |
| 3 | VLLMProcessManager | `models/process.py` + `test_process.py` | 없음 |
| 4 | ModelManager facade | `models/manager.py` + `test_manager.py` | 1, 2, 3 |
| 5 | CLI model 서브커맨드 | `cli.py` 수정 | 4 |
| 6 | models.yaml 예시 | `models.yaml.example` | 1 |
| 7 | Gateway 연동 (P1) | `gateway/app/router.py` 수정 | 4 |

## 10. 에러 처리

| 상황 | 처리 |
|------|------|
| models.yaml 없음 | 기본값 사용, 경고 출력 |
| GGUF 파일 없음 | `FileNotFoundError` + 경로 안내 |
| vLLM 시작 실패 (OOM) | 롤백 + 에러 메시지 (VRAM 부족 안내) |
| vLLM 즉시 크래시 (dead process) | **fail-fast**: returncode 감지 → 120초 대기 없이 즉시 실패 + stderr 출력 |
| vLLM health timeout | 롤백 + 타임아웃 안내 |
| Ctrl+C during switch (좀비 방지) | **signal handler**: 자식 vLLM 프로세스 kill + 정상 종료 |
| CLI→Gateway 통신 실패 | best-effort: Gateway 미실행 시 무시 (CLI 단독 사용 가능) |
| prod에서 switch 시도 | `RuntimeError` + "이미 모든 모델 로드됨" 안내 |
| 존재하지 않는 모델 이름 | `ValueError` + 사용 가능 목록 표시 |
| vLLM 바이너리 없음 | `FileNotFoundError` + 설치 안내 |
