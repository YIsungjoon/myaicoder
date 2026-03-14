"""Model manager — facade for model operations with safety features.

- Prod: launch all Always-on models, no switch needed
- Dev: single model at a time, switch with stop→start + rollback + gateway notify
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx

from myaicoder.models.config import ModelsConfig
from myaicoder.models.process import ProcessState, VLLMInstance, VLLMProcessManager
from myaicoder.models.scanner import ModelScanner


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
        result: list[ModelInfo] = []

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

        Safety:
        - Signal handler: Ctrl+C kills child vLLM (zombie prevention)
        - Dead process detection: fail-fast if vLLM crashes
        - Rollback: restore previous model on failure
        - Gateway notify: HTTP notification after switch
        """
        if self._config.is_prod():
            raise RuntimeError(
                "All models are already loaded (prod environment). "
                "Select via model parameter in Gateway request."
            )

        profile = self._config.get_profile(target_name)
        if not profile:
            available = [p.name for p in self._config.instances]
            raise ValueError(
                f"Unknown model: {target_name}. "
                f"Available: {', '.join(available)}"
            )

        model_path = self._models_dir / profile.file
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        port = self._config.port
        current = self._pm.get_instance(port)
        previous_name = (
            current.model_name
            if current and current.state == ProcessState.READY
            else None
        )

        # Install signal handlers — kill child vLLM on Ctrl+C
        self._pm.install_signal_handlers()

        try:
            # 1. Stop current
            if current and current.state == ProcessState.READY:
                if on_status:
                    on_status(f"Stopping {current.model_name}...")
                await self._pm.stop(port, graceful=True)

            # 2. Start target
            try:
                await self._pm.start(
                    model_path=model_path,
                    model_name=target_name,
                    port=port,
                    vllm_args=profile.vllm_args,
                    on_status=on_status,
                )
            except RuntimeError:
                # Rollback: restart previous model
                if previous_name:
                    if on_status:
                        on_status(f"Failed. Rolling back to {previous_name}...")
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

            # 3. Notify gateway (best-effort)
            await self._notify_gateway(target_name, port)

        finally:
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
        self._pm.install_signal_handlers()

        try:
            if self._config.is_prod():
                profiles = [p for p in self._config.instances if p.always_on]
                return await self._pm.start_all(
                    profiles=profiles,
                    models_dir=self._models_dir,
                    on_status=on_status,
                )
            else:
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
        finally:
            self._pm.uninstall_signal_handlers()

    # ── Internal ──

    async def _notify_gateway(self, model_name: str, port: int) -> None:
        """Notify gateway of model switch (best-effort, non-blocking)."""
        gateway_url = self._config.gateway_url
        if not gateway_url:
            return
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"{gateway_url}/internal/routes/reload",
                    json={"current_model": model_name, "port": port},
                    headers={"X-Internal-Token": self._config.internal_token},
                )
        except Exception:
            pass  # Gateway not running — CLI standalone is fine
