"""SubAgentMiddleware: manages sub-agent delegation via 'task' tool."""

from __future__ import annotations

from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.core.subagent.registry import SubAgentRegistry
from myaicoder.core.subagent.runner import SubAgentRunner
from myaicoder.tools.base import ToolResult

TASK_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "task",
        "description": (
            "Delegate a task to a sub-agent. Use for complex subtasks "
            "that can be worked on independently. The sub-agent has "
            "access to the same tools as you."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "What the sub-agent should do",
                },
                "agent": {
                    "type": "string",
                    "description": (
                        "Sub-agent name (optional, auto-selects if omitted)"
                    ),
                },
            },
            "required": ["description"],
        },
    },
}


class SubAgentMiddleware(AgentMiddleware):
    """Manages sub-agent delegation via 'task' tool.

    DS-02: SubAgentRunner enforces output boundary (≤1000 tokens)
    on all sub-agent results before returning to parent.
    """

    @property
    def name(self) -> str:
        return "subagent"

    @property
    def priority(self) -> int:
        return 40

    def __init__(self, runner: SubAgentRunner, registry: SubAgentRegistry):
        self._runner = runner
        self._registry = registry

    async def before(self, payload: ContextPayload) -> ContextPayload:
        payload = payload.with_tools([TASK_TOOL_SCHEMA])
        agents = self._registry.list_agents()
        if agents:
            names = ", ".join(a.name for a in agents)
            payload = payload.with_instruction(
                f"Available sub-agents: {names}. "
                "Use the 'task' tool to delegate work to them."
            )
        return payload

    async def handle_tool(
        self, tool_name: str, arguments: dict
    ) -> ToolResult | None:
        if tool_name != "task":
            return None

        description = arguments.get("description", "")
        if not description:
            return ToolResult(
                success=False,
                output="",
                error="Task description is required.",
            )

        agent_name = arguments.get("agent")
        result = await self._runner.run(
            task=description, agent_name=agent_name
        )
        return ToolResult(success=True, output=result)
