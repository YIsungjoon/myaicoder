"""Tests for VLLMProvider (requires running vLLM server for integration tests)."""

import os

import pytest

from myaicoder.llm.base import Message
from myaicoder.llm.vllm_provider import VLLMProvider


class TestMessageSerialization:
    def test_user_message(self):
        msg = Message(role="user", content="Hello")
        d = msg.to_openai_dict()
        assert d == {"role": "user", "content": "Hello"}

    def test_assistant_message_with_content(self):
        msg = Message(role="assistant", content="Hi there!")
        d = msg.to_openai_dict()
        assert d == {"role": "assistant", "content": "Hi there!"}

    def test_tool_result_message(self):
        msg = Message(role="tool", content="file contents", tool_call_id="call_123")
        d = msg.to_openai_dict()
        assert d["role"] == "tool"
        assert d["content"] == "file contents"
        assert d["tool_call_id"] == "call_123"


@pytest.mark.skipif(
    not os.environ.get("VLLM_INTEGRATION"),
    reason="Set VLLM_INTEGRATION=1 with running vLLM server on :8001",
)
class TestVLLMIntegration:
    """Integration tests — requires running vLLM server.

    Run: VLLM_INTEGRATION=1 uv run pytest tests/test_llm -q
    """

    @pytest.mark.asyncio
    async def test_health_check(self):
        provider = VLLMProvider(base_url="http://localhost:8001/v1")
        assert await provider.health_check()

    @pytest.mark.asyncio
    async def test_basic_chat(self):
        provider = VLLMProvider(base_url="http://localhost:8001/v1")
        response = await provider.chat(
            messages=[Message(role="user", content="Say hello in one word.")]
        )
        assert response.content is not None
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_streaming_chat(self):
        provider = VLLMProvider(base_url="http://localhost:8001/v1")
        chunks: list[str] = []
        async for chunk in provider.chat_stream(
            messages=[Message(role="user", content="Count from 1 to 5.")]
        ):
            chunks.append(chunk)
        assert len(chunks) > 0
        full = "".join(chunks)
        assert len(full) > 0
