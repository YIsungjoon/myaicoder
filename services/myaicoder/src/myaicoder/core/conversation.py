"""Conversation management with turn-based compression and token budget control.

Key safety feature: Tool call atomicity — tool_calls + tool results are grouped
into Turn blocks and never split during compression. Splitting would cause
400 Bad Request from OpenAI-compatible APIs (missing tool_call_id).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from myaicoder.llm.base import Message

MAX_SUMMARY_CHARS = 2000


@dataclass
class Turn:
    """An atomic conversation turn — cannot be split during compression.

    A turn groups related messages:
    - Simple: [user, assistant]
    - Tool call: [user, assistant(tool_calls), tool, tool, ..., assistant(final)]
    """

    messages: list[Message] = field(default_factory=list)

    @property
    def token_estimate(self) -> int:
        return sum(len(m.content or "") for m in self.messages) // 4

    @property
    def is_tool_turn(self) -> bool:
        return any(m.tool_calls for m in self.messages)

    def summarize(self) -> str:
        """Rule-based summary (no LLM call, deterministic, 0ms latency)."""
        parts: list[str] = []

        for msg in self.messages:
            if msg.role == "user":
                text = (msg.content or "")[:100]
                parts.append(f"User: {text}")

            elif msg.role == "assistant" and msg.tool_calls:
                tool_names = [tc.name for tc in msg.tool_calls]
                parts.append(f"Called: {', '.join(tool_names)}")

            elif msg.role == "tool":
                content_len = len(msg.content or "")
                parts.append(f"Result: {content_len}ch")

            elif msg.role == "assistant":
                text = (msg.content or "")[:100]
                if text:
                    parts.append(f"Assistant: {text}")

        return " → ".join(parts)


class ConversationManager:
    """Manages conversation history with token budget and turn-based compression.

    Compression strategy:
    1. Group messages into atomic Turn blocks (tool call safety)
    2. When over threshold, summarize oldest turns first
    3. Keep recent turns intact (sliding window)
    4. Summary uses oldest-first drop when exceeding MAX_SUMMARY_CHARS
    """

    def __init__(
        self,
        max_tokens: int = 32768,
        compression_threshold: float = 0.8,
        tool_schema_tokens: int = 1000,
        response_buffer: int = 4000,
    ):
        self._history: list[Message] = []
        self._summary: str = ""
        self._max_tokens = max_tokens
        self._compression_threshold = compression_threshold
        self._tool_schema_tokens = tool_schema_tokens
        self._response_buffer = response_buffer
        self._compression_count: int = 0
        self._on_compress: Callable[[int], None] | None = None

    # ── Public API (backward compatible) ──

    def add_message(self, message: Message) -> None:
        self._history.append(message)

    def get_messages(self, system_prompt: str) -> list[Message]:
        """Build full message list. Auto-compress if over threshold."""
        system_tokens = len(system_prompt) // 4
        available = (
            self._max_tokens
            - system_tokens
            - self._tool_schema_tokens
            - self._response_buffer
        )

        if available > 0 and self.estimate_tokens() > available * self._compression_threshold:
            before = self.estimate_tokens()
            self._compress(target_tokens=int(available * 0.6))
            freed = before - self.estimate_tokens()
            if freed > 0 and self._on_compress:
                self._on_compress(freed)

        messages = [Message(role="system", content=system_prompt)]
        if self._summary:
            messages.append(Message(
                role="system",
                content=f"[Previous conversation summary]\n{self._summary}",
            ))
        messages.extend(self._history)
        return messages

    def clear(self) -> None:
        self._history.clear()
        self._summary = ""
        self._compression_count = 0

    @property
    def history(self) -> list[Message]:
        return list(self._history)

    @property
    def message_count(self) -> int:
        return len(self._history)

    def estimate_tokens(self) -> int:
        """Rough token estimate (4 chars ~ 1 token)."""
        total = sum(len(m.content or "") for m in self._history)
        total += len(self._summary)
        return total // 4

    # ── New API ──

    def compact(self) -> int:
        """Manual compression trigger. Returns tokens freed."""
        before = self.estimate_tokens()
        available = self._max_tokens - self._response_buffer - self._tool_schema_tokens
        self._compress(target_tokens=int(available * 0.5))
        return before - self.estimate_tokens()

    @property
    def compression_count(self) -> int:
        return self._compression_count

    @property
    def summary(self) -> str:
        return self._summary

    def set_on_compress(self, callback: Callable[[int], None]) -> None:
        self._on_compress = callback

    # ── Internal: Turn Grouping ──

    @staticmethod
    def _group_into_turns(messages: list[Message]) -> list[Turn]:
        """Group flat message list into atomic Turn blocks.

        Rules:
        - User message starts a new turn
        - Assistant with tool_calls + subsequent Tool messages = same turn
        - Assistant without tool_calls (final response) closes the current turn
        - Tool messages always attach to the current turn (never orphaned)
        """
        if not messages:
            return []

        turns: list[Turn] = []
        current = Turn()

        for msg in messages:
            if msg.role == "user":
                # User starts a new turn — flush previous if non-empty
                if current.messages:
                    turns.append(current)
                    current = Turn()
                current.messages.append(msg)

            elif msg.role == "assistant":
                if not current.messages:
                    current = Turn()
                current.messages.append(msg)

                # Assistant without tool_calls = turn complete
                if not msg.tool_calls:
                    turns.append(current)
                    current = Turn()

            elif msg.role == "tool":
                # Tool result always stays with current turn (atomicity)
                if not current.messages:
                    current = Turn()
                current.messages.append(msg)

        # Flush remaining
        if current.messages:
            turns.append(current)

        return turns

    # ── Internal: Compression ──

    def _compress(self, target_tokens: int) -> None:
        """Compress history to fit within target_tokens.

        Strategy:
        1. Group messages into Turn blocks
        2. Keep recent turns within budget (from newest)
        3. Summarize older turns into summary prefix
        4. Summary uses oldest-first drop when too long
        """
        turns = self._group_into_turns(self._history)

        if not turns:
            return

        # Find split: keep recent turns within budget
        kept_tokens = 0
        split_idx = len(turns)

        for i in range(len(turns) - 1, -1, -1):
            if kept_tokens + turns[i].token_estimate > target_tokens:
                break
            kept_tokens += turns[i].token_estimate
            split_idx = i

        # Ensure at least 1 turn is kept
        if split_idx >= len(turns):
            split_idx = max(0, len(turns) - 1)

        old_turns = turns[:split_idx]
        recent_turns = turns[split_idx:]

        # Generate summary from old turns (oldest-first drop if too long)
        if old_turns:
            self._summary = self._build_summary(old_turns)

        # Rebuild history from recent turns only
        self._history = []
        for turn in recent_turns:
            self._history.extend(turn.messages)

        self._compression_count += 1

    def _build_summary(self, old_turns: list[Turn]) -> str:
        """Build summary with oldest-first drop when exceeding limit.

        Newest summaries are preserved (most relevant to current context).
        Oldest summaries are dropped first.
        """
        # Generate all summaries
        summaries = [t.summarize() for t in old_turns]

        # Include existing summary as oldest entry
        if self._summary:
            summaries.insert(0, f"[Earlier] {self._summary[:200]}")

        # Build from newest to oldest, drop oldest when over limit
        result_parts: list[str] = []
        total_chars = 0

        for summary in reversed(summaries):
            if total_chars + len(summary) + 1 > MAX_SUMMARY_CHARS:
                break
            result_parts.append(summary)
            total_chars += len(summary) + 1

        # Reverse back to chronological order
        result_parts.reverse()

        if not result_parts:
            # Even single newest summary is too long — truncate it
            return summaries[-1][:MAX_SUMMARY_CHARS] if summaries else ""

        return "\n".join(result_parts)
