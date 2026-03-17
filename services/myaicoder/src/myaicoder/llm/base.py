"""LLM Provider interface.

This ABC defines the contract for all LLM providers.
When migrating to TypeScript or Rust, only this interface needs re-implementation.
"""

import json as _json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    def to_openai_dict(self) -> dict:
        """Convert to OpenAI API message format."""
        msg: dict = {"role": self.role}

        if self.content is not None:
            msg["content"] = self.content

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": (
                            tc.arguments
                            if isinstance(tc.arguments, str)
                            else _json.dumps(tc.arguments)
                        ),
                    },
                }
                for tc in self.tool_calls
            ]

        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id

        return msg


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: Usage = field(default_factory=Usage)


class LLMProvider(ABC):
    """Abstract base class for LLM inference providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Send messages and get a complete response."""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Send messages and get a streaming response (text chunks)."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the inference server is reachable."""
        ...
