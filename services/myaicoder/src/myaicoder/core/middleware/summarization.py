"""SummarizationMiddleware: wraps existing ConversationManager compression."""

from __future__ import annotations

from myaicoder.core.conversation import ConversationManager
from myaicoder.core.middleware.base import AgentMiddleware, ContextPayload


class SummarizationMiddleware(AgentMiddleware):
    """Wraps existing ConversationManager's compression logic.

    ConversationManager already handles compression internally during
    get_messages(). This middleware exists for explicit compact triggers
    and to participate in the after() lifecycle.
    """

    @property
    def name(self) -> str:
        return "summarization"

    @property
    def priority(self) -> int:
        return 200  # Runs last in after()

    def __init__(self, conversation: ConversationManager):
        self._conversation = conversation

    async def after(self, payload: ContextPayload) -> ContextPayload:
        # ConversationManager handles auto-compression in get_messages().
        # This hook is reserved for future explicit summarization triggers.
        return payload
