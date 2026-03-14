"""Session persistence — save/load conversation state to JSON files.

Storage layout:
    ~/.config/myaicoder/sessions/
    ├── _index.json                         (session metadata index)
    ├── session_20260314_143000123_a1b2.json (session data)
    └── ...

Session ID format: YYYYMMDD_HHMMSSfff_XXXX
    - fff: milliseconds (000-999)
    - XXXX: 4-digit hex random (collision resistance)
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from myaicoder.core.conversation import ConversationManager
from myaicoder.llm.base import Message, ToolCall


# ── Session ID ──


def _generate_session_id() -> str:
    """Generate collision-resistant session ID.

    Format: YYYYMMDD_HHMMSSfff_XXXX
    Collision probability: ~1/65536 per millisecond.
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S") + f"{now.microsecond // 1000:03d}"
    random_suffix = os.urandom(2).hex()
    return f"{timestamp}_{random_suffix}"


# ── Title ──


def _generate_title(first_user_message: str) -> str:
    """Extract title from first user message (max 50 chars, no LLM)."""
    text = first_user_message.strip()
    title = text.split("\n")[0][:50]
    return title if title else "Untitled session"


# ── Serialization ──


def _serialize_message(msg: Message) -> dict:
    """Convert Message to JSON-serializable dict."""
    d: dict = {"role": msg.role}
    if msg.content is not None:
        d["content"] = msg.content
    if msg.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
            for tc in msg.tool_calls
        ]
    if msg.tool_call_id:
        d["tool_call_id"] = msg.tool_call_id
    return d


def _deserialize_message(d: dict) -> Message:
    """Convert dict to Message. Skips malformed tool_calls gracefully."""
    tool_calls = None
    if "tool_calls" in d:
        tool_calls = []
        for tc in d["tool_calls"]:
            try:
                tool_calls.append(
                    ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                )
            except (KeyError, TypeError):
                continue
        if not tool_calls:
            tool_calls = None
    return Message(
        role=d["role"],
        content=d.get("content"),
        tool_calls=tool_calls,
        tool_call_id=d.get("tool_call_id"),
    )


# ── Atomic Write ──


def _atomic_write(path: Path, data: str) -> None:
    """Write to temp file, then rename (atomic on POSIX)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.rename(path)


# ── Data Model ──


@dataclass
class SessionData:
    """Serializable session state."""

    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    token_estimate: int
    compression_count: int
    summary: str
    messages: list[dict] = field(default_factory=list)


# ── Session Store ──


class SessionStore:
    """File-based session storage with atomic writes."""

    MAX_SESSIONS = 20

    def __init__(self, sessions_dir: Path | None = None):
        self._dir = sessions_dir or Path.home() / ".config" / "myaicoder" / "sessions"

    def save(
        self, conversation: ConversationManager, session_id: str | None = None
    ) -> SessionData:
        """Save conversation state to disk.

        Args:
            conversation: Current ConversationManager
            session_id: Existing ID (update) or None (create new)

        Returns:
            Saved SessionData
        """
        if conversation.message_count == 0:
            raise ValueError("Cannot save empty conversation")

        self._ensure_dir()

        now = datetime.now().isoformat(timespec="milliseconds")
        sid = session_id or _generate_session_id()

        # Find title from first user message
        title = "Untitled session"
        for msg in conversation.history:
            if msg.role == "user" and msg.content:
                title = _generate_title(msg.content)
                break

        # Load existing session for created_at (if updating)
        created_at = now
        if session_id:
            try:
                existing = self._load_session_file(session_id)
                created_at = existing.get("created_at", now)
            except (FileNotFoundError, ValueError):
                pass

        messages = [_serialize_message(m) for m in conversation.history]

        data = SessionData(
            id=sid,
            title=title,
            created_at=created_at,
            updated_at=now,
            message_count=conversation.message_count,
            token_estimate=conversation.estimate_tokens(),
            compression_count=conversation.compression_count,
            summary=conversation.summary,
            messages=messages,
        )

        # Write session file
        session_path = self._dir / f"session_{sid}.json"
        _atomic_write(
            session_path,
            json.dumps(asdict(data), ensure_ascii=False, indent=2),
        )

        # Update index
        index = self._load_index()
        index["last_session_id"] = sid

        # Remove existing entry if updating
        index["sessions"] = [s for s in index["sessions"] if s["id"] != sid]

        # Add new entry at front (most recent)
        index["sessions"].insert(0, {
            "id": sid,
            "title": title,
            "created_at": created_at,
            "updated_at": now,
            "message_count": data.message_count,
        })

        # Prune
        index = self._prune(index)
        self._save_index(index)

        return data

    def load(self, session_id: str) -> SessionData:
        """Load a session by ID.

        Raises:
            FileNotFoundError: Session file not found
            ValueError: Invalid session data
        """
        raw = self._load_session_file(session_id)
        try:
            return SessionData(**{
                k: raw[k]
                for k in SessionData.__dataclass_fields__
            })
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid session data: {e}") from e

    def load_last(self) -> SessionData | None:
        """Load the most recent session. Returns None if no sessions."""
        index = self._load_index()
        last_id = index.get("last_session_id")
        if not last_id:
            return None
        try:
            return self.load(last_id)
        except (FileNotFoundError, ValueError):
            return None

    def list_sessions(self) -> list[dict]:
        """List all sessions from index (no per-file I/O).

        Returns list sorted by updated_at descending.
        """
        index = self._load_index()
        sessions = index.get("sessions", [])
        # Already sorted by most recent first in save()
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session file and remove from index."""
        session_path = self._dir / f"session_{session_id}.json"
        deleted = False
        if session_path.exists():
            session_path.unlink()
            deleted = True

        index = self._load_index()
        before = len(index["sessions"])
        index["sessions"] = [s for s in index["sessions"] if s["id"] != session_id]

        if len(index["sessions"]) < before:
            deleted = True

        # Fix last_session_id if deleted
        if index.get("last_session_id") == session_id:
            index["last_session_id"] = (
                index["sessions"][0]["id"] if index["sessions"] else None
            )

        self._save_index(index)
        return deleted

    # ── Internal ──

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def _load_session_file(self, session_id: str) -> dict:
        """Load raw session JSON."""
        path = self._dir / f"session_{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted session file: {e}") from e

    def _load_index(self) -> dict:
        """Load _index.json with self-healing."""
        index_path = self._dir / "_index.json"
        if not index_path.exists():
            return {"version": 1, "last_session_id": None, "sessions": []}
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "last_session_id": None, "sessions": []}

        # Self-healing: remove entries without files
        if self._dir.exists():
            valid = []
            for s in index.get("sessions", []):
                path = self._dir / f"session_{s['id']}.json"
                if path.exists():
                    valid.append(s)

            if len(valid) != len(index.get("sessions", [])):
                index["sessions"] = valid
                if index.get("last_session_id") and not any(
                    s["id"] == index["last_session_id"] for s in valid
                ):
                    index["last_session_id"] = valid[0]["id"] if valid else None
                self._save_index(index)

        return index

    def _save_index(self, index: dict) -> None:
        self._ensure_dir()
        _atomic_write(
            self._dir / "_index.json",
            json.dumps(index, ensure_ascii=False, indent=2),
        )

    def _prune(self, index: dict) -> dict:
        """Remove oldest sessions beyond MAX_SESSIONS."""
        sessions = index.get("sessions", [])
        if len(sessions) <= self.MAX_SESSIONS:
            return index

        # Keep only MAX_SESSIONS (already sorted most-recent-first)
        to_remove = sessions[self.MAX_SESSIONS:]
        index["sessions"] = sessions[:self.MAX_SESSIONS]

        # Delete session files
        for s in to_remove:
            path = self._dir / f"session_{s['id']}.json"
            if path.exists():
                path.unlink()

        return index
