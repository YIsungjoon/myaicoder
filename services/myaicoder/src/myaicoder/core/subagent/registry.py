"""SubAgentRegistry: register and find sub-agents."""

from __future__ import annotations

from myaicoder.core.subagent.base import SubAgent


class SubAgentRegistry:
    """Registry for available sub-agents."""

    def __init__(self) -> None:
        self._agents: dict[str, SubAgent] = {}

    def register(self, agent: SubAgent) -> None:
        """Register a sub-agent."""
        self._agents[agent.name] = agent

    def get(self, name: str) -> SubAgent | None:
        """Get a sub-agent by exact name."""
        return self._agents.get(name)

    def find_best(self, task_description: str) -> SubAgent:
        """Find best matching agent by keyword, or return general-purpose fallback."""
        task_lower = task_description.lower()

        # Match by keywords first
        for agent in self._agents.values():
            if agent.keywords and any(
                kw.lower() in task_lower for kw in agent.keywords
            ):
                return agent

        # Match by description words
        for agent in self._agents.values():
            desc_words = agent.description.lower().split()
            if any(word in task_lower for word in desc_words if len(word) > 3):
                return agent

        return self._general_purpose()

    def _general_purpose(self) -> SubAgent:
        """Default fallback sub-agent."""
        return SubAgent(
            name="general",
            description="General-purpose sub-agent",
            system_prompt=(
                "You are a helpful coding assistant. "
                "Complete the given task concisely and accurately."
            ),
        )

    def list_agents(self) -> list[SubAgent]:
        """List all registered sub-agents."""
        return list(self._agents.values())

    def __len__(self) -> int:
        return len(self._agents)
