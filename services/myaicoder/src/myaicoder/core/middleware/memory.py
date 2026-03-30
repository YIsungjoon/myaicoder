"""MemoryMiddleware: persistent memory across sessions."""

from __future__ import annotations

from myaicoder.core.memory.loader import AgentsmdLoader
from myaicoder.core.memory.store import MemoryStore
from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload
from myaicoder.tools.base import ToolResult


class MemoryMiddleware(AgentMiddleware):
    """Loads AGENTS.md and persistent memories into system prompt.

    Provides save_memory and recall_memory tools for the agent
    to store and retrieve information across sessions.
    """

    @property
    def name(self) -> str:
        return "memory"

    @property
    def priority(self) -> int:
        return 20  # Load context early

    def __init__(
        self,
        store: MemoryStore,
        loader: AgentsmdLoader | None = None,
    ):
        self._store = store
        self._loader = loader or AgentsmdLoader()

    async def before(self, payload: ContextPayload) -> ContextPayload:
        # AGENTS.md
        agents_md = self._loader.load()
        if agents_md:
            payload = payload.with_instruction(
                f"# Agent Memory (AGENTS.md)\n{agents_md}"
            )

        # Persistent memories
        memories = self._store.recall_recent(limit=10)
        if memories:
            formatted = "\n".join(f"- {m}" for m in memories)
            payload = payload.with_instruction(
                f"# Persistent Memory\n{formatted}"
            )

        # Memory tools
        payload = payload.with_tools(self._store.to_openai_tools())
        return payload

    async def handle_tool(
        self, tool_name: str, arguments: dict
    ) -> ToolResult | None:
        if tool_name == "save_memory":
            content = arguments.get("content", "")
            if not content:
                return ToolResult(
                    success=False, output="", error="Content is required."
                )
            tags = arguments.get("tags", [])
            self._store.save(content, tags)
            return ToolResult(success=True, output="Memory saved.")

        if tool_name == "recall_memory":
            query = arguments.get("query", "")
            results = self._store.search(query)
            if not results:
                return ToolResult(
                    success=True, output="No matching memories found."
                )
            return ToolResult(
                success=True,
                output="\n".join(f"- {r}" for r in results),
            )

        return None
