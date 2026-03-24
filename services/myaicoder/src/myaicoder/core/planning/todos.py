"""TodoList model and write_todos tool schema.

Enables the agent to plan complex tasks before execution,
breaking work into steps and tracking progress.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VALID_STATUSES = ("pending", "in_progress", "done")


@dataclass
class TodoItem:
    """A single plan item."""

    id: str
    content: str
    status: str = "pending"

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            self.status = "pending"


@dataclass
class TodoList:
    """Agent's task plan — a list of TodoItems."""

    items: list[TodoItem] = field(default_factory=list)

    def update(self, todos: list[dict]) -> None:
        """Replace todo list with new items from LLM tool call."""
        self.items = [
            TodoItem(
                id=str(i),
                content=t.get("content", ""),
                status=t.get("status", "pending"),
            )
            for i, t in enumerate(todos)
        ]

    def format(self) -> str:
        """Format for display in system prompt."""
        if not self.items:
            return "(no plan)"
        icons = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]"}
        lines = []
        for item in self.items:
            icon = icons.get(item.status, "[ ]")
            lines.append(f"{icon} {item.content}")
        return "\n".join(lines)

    @property
    def progress(self) -> tuple[int, int]:
        """Return (done_count, total_count)."""
        done = sum(1 for i in self.items if i.status == "done")
        return done, len(self.items)

    def clear(self) -> None:
        """Clear all items."""
        self.items.clear()


def write_todos_tool_schema() -> dict:
    """OpenAI function calling schema for write_todos."""
    return {
        "type": "function",
        "function": {
            "name": "write_todos",
            "description": (
                "Create or update a task plan. Use this to break complex "
                "work into steps and track progress. Call this before "
                "starting multi-step tasks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "What needs to be done",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": list(VALID_STATUSES),
                                    "description": "Current status",
                                },
                            },
                            "required": ["content"],
                        },
                    },
                },
                "required": ["todos"],
            },
        },
    }
