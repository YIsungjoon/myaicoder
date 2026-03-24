"""Sub-agent system: delegate tasks to child agents."""

from myaicoder.core.subagent.base import SubAgent
from myaicoder.core.subagent.registry import SubAgentRegistry
from myaicoder.core.subagent.runner import SubAgentRunner

__all__ = ["SubAgent", "SubAgentRegistry", "SubAgentRunner"]
