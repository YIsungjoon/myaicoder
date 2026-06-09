import asyncio
import contextvars
from typing import Any, Callable
from myaicoder.tools.base import Tool, ToolResult

# ContextVar to share the progress callback with tools executing in the agent loop
progress_ctx: contextvars.ContextVar[Callable[[str], Any] | None] = contextvars.ContextVar("progress_ctx", default=None)

# Global variables to handle user prompt blocking
_user_answer_event = asyncio.Event()
_user_answer_value = ""


class AskUserTool(Tool):
    """Tool for asking the user a question to clarify requirements or get approval."""

    @property
    def name(self) -> str:
        return "AskUser"

    @property
    def description(self) -> str:
        return (
            "Ask the user a question to clarify requirements, resolve ambiguity, "
            "or request instructions when stuck. Blocks until the user answers."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user.",
                }
            },
            "required": ["question"],
        }

    async def execute(self, question: str) -> ToolResult:
        global _user_answer_event, _user_answer_value

        # Reset the event
        _user_answer_value = ""
        _user_answer_event.clear()

        # Send progress log with special prefix [ASK_USER]:
        on_progress = progress_ctx.get()
        if on_progress:
            import inspect
            msg = f"[ASK_USER]:{question}"
            if inspect.iscoroutinefunction(on_progress):
                await on_progress(msg)
            else:
                on_progress(msg)

        # Block until submit_answer tool sets the event
        await _user_answer_event.wait()

        return ToolResult(
            success=True,
            output=_user_answer_value,
            error=None,
        )


class SubmitAnswerTool(Tool):
    """Tool triggered by client to submit the user's answer to a pending question."""

    @property
    def name(self) -> str:
        return "SubmitAnswer"

    @property
    def description(self) -> str:
        return (
            "Submit the user's answer to the pending question. "
            "This unblocks the agent."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The user's answer to the pending question.",
                }
            },
            "required": ["answer"],
        }

    async def execute(self, answer: str) -> ToolResult:
        global _user_answer_event, _user_answer_value

        # Set the value and trigger the event to unblock AskUser
        _user_answer_value = answer
        _user_answer_event.set()

        return ToolResult(
            success=True,
            output="Answer submitted successfully.",
            error=None,
        )
