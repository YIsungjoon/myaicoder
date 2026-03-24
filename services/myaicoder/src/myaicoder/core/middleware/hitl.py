"""HITLMiddleware: human-in-the-loop approval gate."""

from __future__ import annotations

from collections.abc import Callable

from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.tools.base import ToolResult


class HITLMiddleware(AgentMiddleware):
    """Human-in-the-loop approval gate.

    Checks tool calls against require_approval set. If denied, returns
    an error ToolResult. If approved (or not required), returns None
    to let the next middleware handle execution.
    """

    @property
    def name(self) -> str:
        return "hitl"

    @property
    def priority(self) -> int:
        return 10  # Runs first — deny early before execution

    def __init__(
        self,
        callback: Callable[[str, dict], bool] | None = None,
        require_approval: set[str] | None = None,
    ):
        self._callback = callback
        self._require_approval = require_approval or set()

    async def handle_tool(
        self, tool_name: str, arguments: dict
    ) -> ToolResult | None:
        if tool_name not in self._require_approval:
            return None  # No approval needed — pass to next middleware

        if self._callback and not self._callback(tool_name, arguments):
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' execution denied by user.",
            )

        return None  # Approved — let next middleware execute
