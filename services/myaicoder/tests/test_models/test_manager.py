"""Tests for ModelManager — list, switch workflow, rollback, prod guard."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from myaicoder.models.config import ModelProfile, ModelsConfig
from myaicoder.models.manager import ModelManager, ModelStatus
from myaicoder.models.process import ProcessState, VLLMInstance, VLLMProcessManager
from myaicoder.models.scanner import ModelScanner


def _dev_config(models_dir: str = "/tmp/models") -> ModelsConfig:
    return ModelsConfig(
        environment="dev",
        models_dir=models_dir,
        default_model="small",
        port=8001,
        instances=[
            ModelProfile(name="small", file="small.gguf", description="Small model"),
            ModelProfile(name="big", file="big.gguf", description="Big model"),
        ],
    )


def _prod_config() -> ModelsConfig:
    return ModelsConfig(
        environment="prod",
        instances=[
            ModelProfile(name="a", file="a.gguf", port=8001, always_on=True),
            ModelProfile(name="b", file="b.gguf", port=8002, always_on=True),
        ],
    )


class TestListModels:
    def test_list_with_files(self, tmp_path: Path):
        config = _dev_config(str(tmp_path))
        (tmp_path / "small.gguf").write_bytes(b"x" * 1024)
        # big.gguf not present → NOT_FOUND

        pm = VLLMProcessManager()
        scanner = ModelScanner(tmp_path, config)
        mgr = ModelManager(config, pm, scanner)

        models = mgr.list_models()
        assert len(models) == 2

        small = next(m for m in models if m.name == "small")
        assert small.status == ModelStatus.AVAILABLE
        assert small.size_human != "?"

        big = next(m for m in models if m.name == "big")
        assert big.status == ModelStatus.NOT_FOUND
        assert big.size_human == "?"

    def test_list_with_running_model(self, tmp_path: Path):
        config = _dev_config(str(tmp_path))
        (tmp_path / "small.gguf").write_bytes(b"x" * 1024)

        pm = VLLMProcessManager()
        # Simulate running instance
        pm._instances[8001] = VLLMInstance(
            model_name="small",
            model_path=tmp_path / "small.gguf",
            port=8001,
            state=ProcessState.READY,
        )
        scanner = ModelScanner(tmp_path, config)
        mgr = ModelManager(config, pm, scanner)

        models = mgr.list_models()
        small = next(m for m in models if m.name == "small")
        assert small.status == ModelStatus.LOADED
        assert small.port == 8001


class TestSwitchModel:
    @pytest.mark.asyncio
    async def test_prod_switch_rejected(self):
        """Switch on prod environment raises RuntimeError."""
        config = _prod_config()
        pm = VLLMProcessManager()
        scanner = ModelScanner("/tmp", config)
        mgr = ModelManager(config, pm, scanner)

        with pytest.raises(RuntimeError, match="already loaded"):
            await mgr.switch_model("a")

    @pytest.mark.asyncio
    async def test_unknown_model_rejected(self, tmp_path: Path):
        """Switch to unknown model raises ValueError."""
        config = _dev_config(str(tmp_path))
        pm = VLLMProcessManager()
        scanner = ModelScanner(tmp_path, config)
        mgr = ModelManager(config, pm, scanner)

        with pytest.raises(ValueError, match="Unknown model"):
            await mgr.switch_model("nonexistent")

    @pytest.mark.asyncio
    async def test_missing_file_rejected(self, tmp_path: Path):
        """Switch with missing GGUF file raises FileNotFoundError."""
        config = _dev_config(str(tmp_path))
        # Don't create big.gguf
        pm = VLLMProcessManager()
        scanner = ModelScanner(tmp_path, config)
        mgr = ModelManager(config, pm, scanner)

        with pytest.raises(FileNotFoundError):
            await mgr.switch_model("big")

    @pytest.mark.asyncio
    async def test_switch_success(self, tmp_path: Path):
        """Successful switch: stop current → start target → notify gateway."""
        config = _dev_config(str(tmp_path))
        (tmp_path / "big.gguf").write_bytes(b"x" * 1024)

        pm = VLLMProcessManager()
        # Simulate current running model
        pm._instances[8001] = VLLMInstance(
            model_name="small",
            model_path=tmp_path / "small.gguf",
            port=8001,
            state=ProcessState.READY,
        )

        scanner = ModelScanner(tmp_path, config)
        mgr = ModelManager(config, pm, scanner)

        statuses: list[str] = []

        with (
            patch.object(pm, "stop", new_callable=AsyncMock) as mock_stop,
            patch.object(pm, "start", new_callable=AsyncMock) as mock_start,
            patch.object(mgr, "_notify_gateway", new_callable=AsyncMock) as mock_notify,
        ):
            mock_start.return_value = VLLMInstance(
                model_name="big",
                model_path=tmp_path / "big.gguf",
                port=8001,
                state=ProcessState.READY,
            )

            result = await mgr.switch_model("big", on_status=statuses.append)

        assert result.name == "big"
        assert result.status == ModelStatus.LOADED
        mock_stop.assert_called_once_with(8001, graceful=True)
        mock_start.assert_called_once()
        mock_notify.assert_called_once_with("big", 8001)

    @pytest.mark.asyncio
    async def test_switch_rollback_on_failure(self, tmp_path: Path):
        """Failed switch rolls back to previous model."""
        config = _dev_config(str(tmp_path))
        (tmp_path / "small.gguf").write_bytes(b"x" * 1024)
        (tmp_path / "big.gguf").write_bytes(b"x" * 1024)

        pm = VLLMProcessManager()
        pm._instances[8001] = VLLMInstance(
            model_name="small",
            model_path=tmp_path / "small.gguf",
            port=8001,
            state=ProcessState.READY,
        )

        scanner = ModelScanner(tmp_path, config)
        mgr = ModelManager(config, pm, scanner)

        call_count = 0

        async def mock_start(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (target) fails
                raise RuntimeError("OOM")
            # Second call (rollback) succeeds
            return VLLMInstance(
                model_name="small",
                model_path=tmp_path / "small.gguf",
                port=8001,
                state=ProcessState.READY,
            )

        with (
            patch.object(pm, "stop", new_callable=AsyncMock),
            patch.object(pm, "start", side_effect=mock_start),
        ):
            with pytest.raises(RuntimeError, match="OOM"):
                await mgr.switch_model("big")

        # Rollback was attempted
        assert call_count == 2


class TestGetStatus:
    def test_status_empty(self):
        config = _dev_config()
        pm = VLLMProcessManager()
        scanner = ModelScanner("/tmp", config)
        mgr = ModelManager(config, pm, scanner)

        status = mgr.get_status()
        assert status["environment"] == "dev"
        assert status["loaded_models"] == 0
        assert status["total_models"] == 2


class TestGatewayNotify:
    @pytest.mark.asyncio
    async def test_notify_skipped_without_url(self):
        """No gateway_url → skip notification silently."""
        config = _dev_config()  # gateway_url is empty
        pm = VLLMProcessManager()
        scanner = ModelScanner("/tmp", config)
        mgr = ModelManager(config, pm, scanner)

        # Should not raise
        await mgr._notify_gateway("test", 8001)

    @pytest.mark.asyncio
    async def test_notify_tolerates_connection_error(self):
        """Gateway unreachable → swallow error (best-effort)."""
        config = _dev_config()
        config.gateway_url = "http://localhost:99999"
        pm = VLLMProcessManager()
        scanner = ModelScanner("/tmp", config)
        mgr = ModelManager(config, pm, scanner)

        # Should not raise even with invalid URL
        await mgr._notify_gateway("test", 8001)
