"""PlanningMiddleware: injects write_todos tool and tracks agent planning."""

from __future__ import annotations

from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.core.planning.todos import TodoList, write_todos_tool_schema
from myaicoder.tools.base import ToolResult


class PlanningMiddleware(AgentMiddleware):
    """Enables agent to plan complex tasks before execution.

    Injects write_todos tool and current plan state into the system prompt.
    """

    @property
    def name(self) -> str:
        return "planning"

    @property
    def priority(self) -> int:
        return 30

    def __init__(self, todos: TodoList | None = None):
        self._todos = todos or TodoList()

    async def before(self, payload: ContextPayload) -> ContextPayload:
        payload = payload.with_tools([write_todos_tool_schema()])
        payload = payload.with_instruction(
            "You have a write_todos tool. Use it to plan complex tasks "
            "before execution. Break work into steps and track progress."
        )
        if self._todos.items:
            done, total = self._todos.progress
            payload = payload.with_instruction(
                f"Current plan ({done}/{total} done):\n{self._todos.format()}"
            )
        return payload

    async def handle_tool(
        self, tool_name: str, arguments: dict
    ) -> ToolResult | None:
        if tool_name != "write_todos":
            return None
        self._todos.update(arguments.get("todos", []))
        done, total = self._todos.progress
        return ToolResult(
            success=True,
            output=f"Plan updated ({done}/{total} done):\n{self._todos.format()}",
        )

    @property
    def todos(self) -> TodoList:
        return self._todos
