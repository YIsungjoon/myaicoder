"""OpenAI-compatible LLM provider (vLLM, llama-cpp-python, etc.)."""

import json
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI

from myaicoder.llm.base import LLMProvider, LLMResponse, Message, ToolCall, Usage


class VLLMProvider(LLMProvider):
    """LLM provider that connects to any OpenAI-compatible API server.

    Supports vLLM, llama-cpp-python, llama.cpp server, Ollama, etc.
    Handles Qwen3.5's reasoning_content field (thinking mode).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080/v1",
        model: str = "Qwen3.5-27B-Q4_0.gguf",
        api_key: str = "not-needed",
        max_tokens: int = 8192,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.base_url = base_url
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        openai_messages = [m.to_openai_dict() for m in messages]

        kwargs: dict = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Use raw httpx to capture reasoning_content (Qwen3.5 thinking mode)
        raw_response = await self._raw_chat(openai_messages, kwargs)

        content = raw_response.get("content", "") or ""
        reasoning = raw_response.get("reasoning_content", "")

        # If content is empty but reasoning exists, use reasoning as content
        # This handles Qwen3.5 thinking mode where content may be empty
        if not content and reasoning:
            content = reasoning

        # Store reasoning separately for potential UI display
        self._last_reasoning = reasoning if reasoning else None

        # Parse tool calls if present
        parsed_tool_calls = None
        raw_tool_calls = raw_response.get("tool_calls")
        if raw_tool_calls:
            parsed_tool_calls = []
            for tc in raw_tool_calls:
                arguments = tc["function"]["arguments"]
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {"raw": arguments}

                parsed_tool_calls.append(
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=arguments,
                    )
                )

        raw_usage = raw_response.get("_usage", {})
        usage = Usage(
            prompt_tokens=raw_usage.get("prompt_tokens", 0),
            completion_tokens=raw_usage.get("completion_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            usage=usage,
        )

    async def _raw_chat(self, messages: list[dict], kwargs: dict) -> dict:
        """Make raw HTTP request to capture all fields including reasoning_content."""
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.0),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        if "tools" in kwargs:
            payload["tools"] = kwargs["tools"]
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]["message"]
        choice["_usage"] = data.get("usage", {})
        return choice

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        openai_messages = [m.to_openai_dict() for m in messages]

        kwargs: dict = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
