"""Tests for VLLMProvider (requires running vLLM server for integration tests)."""

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
    True,  # Set to False when vLLM server is running
    reason="Integration test: requires running vLLM server",
)
class TestVLLMIntegration:
    @pytest.mark.asyncio
    async def test_health_check(self):
        provider = VLLMProvider()
        assert await provider.health_check()

    @pytest.mark.asyncio
    async def test_basic_chat(self):
        provider = VLLMProvider()
        response = await provider.chat(
            messages=[Message(role="user", content="Say hello in one word.")]
        )
        assert response.content is not None
        assert len(response.content) > 0
