"""Shared test fixtures."""

import pytest

from myaicoder.llm.base import LLMProvider, LLMResponse, Usage


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing without a real vLLM server."""

    def __init__(self, responses: list[LLMResponse] | list[str] | None = None):
        if responses and isinstance(responses[0], str):
            self._responses = [
                LLMResponse(
                    content=r,
                    usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
                )
                for r in responses
            ]
        elif responses:
            self._responses = responses
        else:
            self._responses = [
                LLMResponse(
                    content="Hello! I'm a mock AI assistant.",
                    usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
                )
            ]
        self._call_index = 0

    async def chat(self, messages, tools=None, temperature=0.0):
        resp = self._responses[self._call_index % len(self._responses)]
        self._call_index += 1
        return resp

    async def chat_stream(self, messages, tools=None, temperature=0.0):
        resp = self._responses[self._call_index % len(self._responses)]
        self._call_index += 1
        text = resp.content or ""
        for word in text.split():
            yield word + " "

    async def health_check(self):
        return True


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture
def mock_llm_with_responses():
    def _factory(responses):
        return MockLLMProvider(responses=responses)
    return _factory
