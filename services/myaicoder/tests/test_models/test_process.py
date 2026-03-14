"""Tests for VLLMProcessManager — command building, state, dead process detection."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from myaicoder.models.config import LlamaCppArgs, VLLMArgs
from myaicoder.models.process import ProcessState, VLLMInstance, VLLMProcessManager


class TestBuildCommandVLLM:
    def test_basic_vllm_command(self):
        pm = VLLMProcessManager(backend="vllm", command="vllm")
        cmd = pm._build_command(Path("/models/test.gguf"), 8001)
        assert cmd == [
            "vllm", "serve", "/models/test.gguf",
            "--host", "0.0.0.0",
            "--port", "8001",
        ]

    def test_vllm_command_with_args(self):
        pm = VLLMProcessManager(backend="vllm", command="vllm")
        args = VLLMArgs(
            gpu_memory_utilization=0.5,
            max_model_len=4096,
            extra_args=["--dtype", "float16"],
        )
        cmd = pm._build_command(Path("/models/test.gguf"), 9001, vllm_args=args)
        assert "--gpu-memory-utilization" in cmd
        assert "0.5" in cmd
        assert "--max-model-len" in cmd
        assert "4096" in cmd
        assert "--dtype" in cmd
        assert "float16" in cmd


class TestBuildCommandLlamaCpp:
    def test_basic_llama_cpp_command(self):
        pm = VLLMProcessManager(backend="llama-cpp", command="llama-server")
        cmd = pm._build_command(Path("/models/test.gguf"), 8001)
        assert cmd == [
            "llama-server",
            "--model", "/models/test.gguf",
            "--host", "0.0.0.0",
            "--port", "8001",
            "--n-gpu-layers", "-1",
        ]

    def test_llama_cpp_command_with_args(self):
        pm = VLLMProcessManager(backend="llama-cpp", command="llama-server")
        args = LlamaCppArgs(n_gpu_layers=32, ctx_size=16384, extra_args=["--flash-attn"])
        cmd = pm._build_command(
            Path("/models/test.gguf"), 8001, llama_cpp_args=args
        )
        assert "--model" in cmd
        assert "--n-gpu-layers" in cmd
        assert "32" in cmd
        assert "--ctx-size" in cmd
        assert "16384" in cmd
        assert "--flash-attn" in cmd


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy_server(self):
        pm = VLLMProcessManager()
        with patch("myaicoder.models.process.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await pm.health_check(8001)
            assert result is True

    @pytest.mark.asyncio
    async def test_unreachable_server(self):
        pm = VLLMProcessManager()
        with patch("myaicoder.models.process.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await pm.health_check(8001)
            assert result is False


class TestDeadProcessDetection:
    @pytest.mark.asyncio
    async def test_dead_process_raises_immediately(self):
        """If server crashes on startup, don't wait 120s — fail fast."""
        pm = VLLMProcessManager()

        mock_proc = MagicMock()
        mock_proc.returncode = 1

        mock_stderr = AsyncMock()
        mock_stderr.read = AsyncMock(return_value=b"CUDA out of memory")
        mock_proc.stderr = mock_stderr

        instance = VLLMInstance(
            model_name="test-model",
            model_path=Path("/test.gguf"),
            port=8001,
            state=ProcessState.STARTING,
            process=mock_proc,
        )
        pm._instances[8001] = instance

        with pytest.raises(RuntimeError, match="exited immediately"):
            await pm._wait_for_health(8001, timeout=5)


class TestInstanceManagement:
    def test_get_running_empty(self):
        pm = VLLMProcessManager()
        assert pm.get_running() == []

    def test_get_running_filters_ready(self):
        pm = VLLMProcessManager()
        pm._instances[8001] = VLLMInstance(
            model_name="a", model_path=Path("/a.gguf"), port=8001,
            state=ProcessState.READY,
        )
        pm._instances[8002] = VLLMInstance(
            model_name="b", model_path=Path("/b.gguf"), port=8002,
            state=ProcessState.STOPPED,
        )
        running = pm.get_running()
        assert len(running) == 1
        assert running[0].model_name == "a"

    def test_get_instance(self):
        pm = VLLMProcessManager()
        pm._instances[8001] = VLLMInstance(
            model_name="test", model_path=Path("/t.gguf"), port=8001,
        )
        assert pm.get_instance(8001) is not None
        assert pm.get_instance(9999) is None


class TestBinaryCheck:
    @pytest.mark.asyncio
    async def test_missing_binary_gives_clear_error(self):
        """Missing server binary raises with user-friendly message."""
        pm = VLLMProcessManager(command="nonexistent-binary-xyz")
        with pytest.raises(RuntimeError, match="not found"):
            await pm.start(
                model_path=Path("/fake/model.gguf"),
                model_name="test",
                port=8001,
            )


class TestSignalHandlers:
    def test_install_and_uninstall(self):
        """Signal handlers can be installed and restored without error."""
        pm = VLLMProcessManager()
        pm.install_signal_handlers()
        pm.uninstall_signal_handlers()
