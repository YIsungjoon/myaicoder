"""MemoryStore: persistent memory storage (JSON file-based, atomic write)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class MemoryStore:
    """Persistent memory storage for agent learning across sessions.

    Stores memories as JSON with content, tags, and timestamps.
    Uses atomic write (tmp + rename) to prevent corruption.
    """

    def __init__(self, storage_dir: Path | None = None):
        self._dir = storage_dir or (
            Path.home() / ".config" / "myaicoder" / "memory"
        )
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "memories.json"
        self._memories: list[dict] = self._load()

    def save(self, content: str, tags: list[str] | None = None) -> None:
        """Save a memory entry."""
        self._memories.append({
            "content": content,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
        })
        self._persist()

    def recall_recent(self, limit: int = 10) -> list[str]:
        """Recall most recent memories."""
        return [m["content"] for m in self._memories[-limit:]]

    def search(self, query: str) -> list[str]:
        """Search memories by content or tags."""
        if not query:
            return self.recall_recent()
        query_lower = query.lower()
        results = [
            m["content"]
            for m in self._memories
            if query_lower in m["content"].lower()
            or any(query_lower in t.lower() for t in m.get("tags", []))
        ]
        return results[-10:]

    def clear(self) -> None:
        """Clear all memories."""
        self._memories.clear()
        self._persist()

    @property
    def count(self) -> int:
        return len(self._memories)

    def to_openai_tools(self) -> list[dict]:
        """Return save_memory and recall_memory tool schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "save_memory",
                    "description": (
                        "Save important information for future sessions. "
                        "Use this to remember project context, decisions, "
                        "or learned patterns."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "What to remember",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags for categorization",
                            },
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "recall_memory",
                    "description": (
                        "Search persistent memory for relevant information "
                        "from previous sessions."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            },
                        },
                    },
                },
            },
        ]

    def _load(self) -> list[dict]:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _persist(self) -> None:
        """Atomic write: write to tmp, then rename."""
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._memories, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._file)
