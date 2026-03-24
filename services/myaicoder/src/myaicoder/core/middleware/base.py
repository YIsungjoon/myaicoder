"""Core middleware interfaces: ContextPayload and AgentMiddleware ABC.

DS-01: ContextPayload is frozen (immutable). Middleware uses with_*() methods
to return new payloads. Direct mutation raises FrozenInstanceError.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

from myaicoder.llm.base import Message
from myaicoder.tools.base import ToolResult


@dataclass(frozen=True)
class ContextPayload:
    """Structurally immutable context passed through middleware stack.

    frozen=True + tuple = compile-time level immutability.
    Each middleware returns a new payload via with_*() methods.
    """

    messages: tuple[Message, ...] = field(default_factory=tuple)
    system_instructions: tuple[str, ...] = field(default_factory=tuple)
    tools: tuple[dict, ...] = field(default_factory=tuple)
    metadata: dict = field(default_factory=dict)

    def with_instruction(self, instruction: str) -> ContextPayload:
        """Add a system instruction (returns new payload)."""
        return replace(
            self, system_instructions=self.system_instructions + (instruction,)
        )

    def with_tools(self, tools: list[dict]) -> ContextPayload:
        """Add tools (returns new payload)."""
        return replace(self, tools=self.tools + tuple(tools))

    def with_metadata(self, key: str, value: object) -> ContextPayload:
        """Set metadata key (returns new payload with shallow-copied dict)."""
        return replace(self, metadata={**self.metadata, key: value})


class AgentMiddleware(ABC):
    """Base class for all middleware in the agent pipeline.

    Lifecycle:
    1. before() — inject tools/instructions into payload (pre-LLM)
    2. handle_tool() — handle tool calls (chain of responsibility)
    3. after() — post-processing (reverse priority order)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique middleware identifier."""
        ...

    @property
    def priority(self) -> int:
        """Execution order. Lower = earlier. Default 100."""
        return 100

    async def before(self, payload: ContextPayload) -> ContextPayload:
        """Pre-LLM hook. Use payload.with_*() to add instructions/tools."""
        return payload

    async def handle_tool(
        self, tool_name: str, arguments: dict
    ) -> ToolResult | None:
        """Handle a tool call. Return None to pass to next middleware."""
        return None

    async def after(self, payload: ContextPayload) -> ContextPayload:
        """Post-LLM hook. Process response, update state."""
        return payload
