"""Conversation management with history and token tracking."""

from myaicoder.llm.base import Message


class ConversationManager:
    """Manages conversation history and token budget."""

    def __init__(self, max_tokens: int = 32768):
        self._history: list[Message] = []
        self._max_tokens = max_tokens

    def add_message(self, message: Message) -> None:
        self._history.append(message)

    def get_messages(self, system_prompt: str) -> list[Message]:
        """Build full message list with system prompt + history."""
        messages = [Message(role="system", content=system_prompt)]
        messages.extend(self._history)
        return messages

    def clear(self) -> None:
        self._history.clear()

    @property
    def history(self) -> list[Message]:
        return list(self._history)

    @property
    def message_count(self) -> int:
        return len(self._history)

    def estimate_tokens(self) -> int:
        """Rough token estimate (4 chars ≈ 1 token)."""
        total_chars = sum(len(m.content or "") for m in self._history)
        return total_chars // 4
