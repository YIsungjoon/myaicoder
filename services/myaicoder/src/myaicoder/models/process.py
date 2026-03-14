"""vLLM process lifecycle management — start, stop, health check, signal safety."""

from __future__ import annotations

import asyncio
import shutil
import signal
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import httpx

from myaicoder.models.config import LlamaCppArgs, VLLMArgs


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
    process: asyncio.subprocess.Process | None = field(default=None, repr=False)
    pid: int | None = None


class VLLMProcessManager:
    """Manages LLM server processes (llama.cpp or vLLM) with safety features.

    - Supports both llama-cpp (llama-server) and vLLM backends
    - Dead process detection: fail-fast if server crashes on startup
    - Signal handlers: kill child processes on Ctrl+C (zombie prevention)
    """

    def __init__(self, backend: str = "llama-cpp", command: str = ""):
        self._instances: dict[int, VLLMInstance] = {}
        self._backend = backend
        if command:
            self._cmd = command
        elif backend == "llama-cpp":
            self._cmd = "llama-server"
        else:
            self._cmd = "vllm"
        self._original_sigint: signal.Handlers | None = None
        self._original_sigterm: signal.Handlers | None = None

    # ── Lifecycle ──

    async def start(
        self,
        model_path: Path,
        model_name: str,
        port: int,
        vllm_args: VLLMArgs | None = None,
        llama_cpp_args: LlamaCppArgs | None = None,
        on_status: Callable[[str], None] | None = None,
        health_timeout: int = 120,
    ) -> VLLMInstance:
        """Start an LLM server process on the given port."""
        instance = VLLMInstance(
            model_name=model_name,
            model_path=model_path,
            port=port,
            state=ProcessState.STARTING,
        )
        self._instances[port] = instance

        if not shutil.which(self._cmd):
            if self._backend == "llama-cpp":
                hint = "Build from source: https://github.com/ggml-org/llama.cpp"
            else:
                hint = "Install with: pip install vllm"
            raise RuntimeError(
                f"LLM server not found: '{self._cmd}'. {hint}"
            )

        if on_status:
            on_status(f"Loading {model_name} on :{port}...")

        cmd = self._build_command(model_path, port, vllm_args, llama_cpp_args)
        instance.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        instance.pid = instance.process.pid

        ready = await self._wait_for_health(port, timeout=health_timeout)
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
        """Stop vLLM process on port."""
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
        profiles: list,
        models_dir: Path,
        on_status: Callable[[str], None] | None = None,
    ) -> list[VLLMInstance]:
        """Start multiple vLLM instances sequentially (prod mode).

        Sequential to avoid memory spike — vLLM uses massive VRAM during weight loading.
        """
        results: list[VLLMInstance] = []
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
        """Check if vLLM on port is healthy via GET /health."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"http://localhost:{port}/health")
                return resp.status_code == 200
        except Exception:
            return False

    def get_instance(self, port: int) -> VLLMInstance | None:
        return self._instances.get(port)

    def get_running(self) -> list[VLLMInstance]:
        return [i for i in self._instances.values() if i.state == ProcessState.READY]

    # ── Internal ──

    def _build_command(
        self,
        model_path: Path,
        port: int,
        vllm_args: VLLMArgs | None = None,
        llama_cpp_args: LlamaCppArgs | None = None,
    ) -> list[str]:
        if self._backend == "llama-cpp":
            return self._build_llama_cpp_command(model_path, port, llama_cpp_args)
        return self._build_vllm_command(model_path, port, vllm_args)

    def _build_vllm_command(
        self, model_path: Path, port: int, args: VLLMArgs | None
    ) -> list[str]:
        cmd = [
            self._cmd, "serve", str(model_path),
            "--host", "0.0.0.0",
            "--port", str(port),
        ]
        if args:
            cmd.extend(["--gpu-memory-utilization", str(args.gpu_memory_utilization)])
            cmd.extend(["--max-model-len", str(args.max_model_len)])
            cmd.extend(args.extra_args)
        return cmd

    def _build_llama_cpp_command(
        self, model_path: Path, port: int, args: LlamaCppArgs | None
    ) -> list[str]:
        cmd = [
            self._cmd,
            "--model", str(model_path),
            "--host", "0.0.0.0",
            "--port", str(port),
        ]
        if args:
            cmd.extend(["--n-gpu-layers", str(args.n_gpu_layers)])
            cmd.extend(["--ctx-size", str(args.ctx_size)])
            cmd.extend(args.extra_args)
        else:
            cmd.extend(["--n-gpu-layers", "-1"])
        return cmd

    async def _wait_for_health(self, port: int, timeout: int = 120) -> bool:
        """Poll /health until ready or timeout.

        Fail-fast: if the process has already exited (dead process detection),
        raise immediately instead of polling for 120s.
        """
        instance = self._instances.get(port)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout

        while loop.time() < deadline:
            # Dead process detection
            if instance and instance.process and instance.process.returncode is not None:
                stderr_text = ""
                if instance.process.stderr:
                    raw = await instance.process.stderr.read()
                    stderr_text = raw.decode(errors="replace")
                raise RuntimeError(
                    f"vLLM process exited immediately "
                    f"(code={instance.process.returncode}). "
                    f"Likely cause: VRAM OOM or invalid model.\n"
                    f"{stderr_text[:500]}"
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

        Prevents zombie/orphan processes when CLI is Ctrl+C'd during switch.
        """
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)

        def _cleanup(signum: int, frame: object) -> None:
            for inst in self._instances.values():
                if inst.process and inst.process.returncode is None:
                    inst.process.kill()
            signal.signal(signum, signal.SIG_DFL)
            raise SystemExit(128 + signum)

        signal.signal(signal.SIGINT, _cleanup)
        signal.signal(signal.SIGTERM, _cleanup)

    def uninstall_signal_handlers(self) -> None:
        """Restore original signal handlers after operation completes."""
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
