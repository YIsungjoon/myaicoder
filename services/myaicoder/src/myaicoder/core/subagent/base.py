"""SubAgent: declarative sub-agent specification."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubAgent:
    """Declarative sub-agent spec.

    Attributes:
        name: Unique identifier for matching.
        description: What this agent specializes in (used for auto-matching).
        system_prompt: Additional system prompt for the sub-agent.
        tools_override: Tool names to use (None = inherit parent's tools).
        max_iterations: Max tool loop iterations for this sub-agent.
    """

    name: str
    description: str
    system_prompt: str = ""
    tools_override: list[str] | None = None
    max_iterations: int = 15
    keywords: list[str] = field(default_factory=list)
