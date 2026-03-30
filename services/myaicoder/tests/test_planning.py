"""Tests for Planning system (TodoList + PlanningMiddleware)."""

import pytest

from myaicoder.core.middleware.base import ContextPayload
from myaicoder.core.middleware.planning import PlanningMiddleware
from myaicoder.core.planning.todos import TodoItem, TodoList, write_todos_tool_schema


class TestTodoItem:
    def test_default_status(self):
        item = TodoItem(id="0", content="test")
        assert item.status == "pending"

    def test_invalid_status_defaults_to_pending(self):
        item = TodoItem(id="0", content="test", status="invalid")
        assert item.status == "pending"

    def test_valid_statuses(self):
        for status in ("pending", "in_progress", "done"):
            item = TodoItem(id="0", content="test", status=status)
            assert item.status == status


class TestTodoList:
    def test_empty_format(self):
        todos = TodoList()
        assert todos.format() == "(no plan)"

    def test_update_from_dicts(self):
        todos = TodoList()
        todos.update([
            {"content": "step 1"},
            {"content": "step 2", "status": "done"},
        ])
        assert len(todos.items) == 2
        assert todos.items[0].status == "pending"
        assert todos.items[1].status == "done"

    def test_format_with_items(self):
        todos = TodoList()
        todos.update([
            {"content": "first", "status": "done"},
            {"content": "second", "status": "in_progress"},
            {"content": "third"},
        ])
        formatted = todos.format()
        assert "[x] first" in formatted
        assert "[~] second" in formatted
        assert "[ ] third" in formatted

    def test_progress(self):
        todos = TodoList()
        todos.update([
            {"content": "a", "status": "done"},
            {"content": "b", "status": "done"},
            {"content": "c"},
        ])
        done, total = todos.progress
        assert done == 2
        assert total == 3

    def test_progress_empty(self):
        assert TodoList().progress == (0, 0)

    def test_clear(self):
        todos = TodoList()
        todos.update([{"content": "x"}])
        todos.clear()
        assert len(todos.items) == 0

    def test_update_replaces(self):
        todos = TodoList()
        todos.update([{"content": "old"}])
        todos.update([{"content": "new"}])
        assert len(todos.items) == 1
        assert todos.items[0].content == "new"


class TestWriteTodosToolSchema:
    def test_schema_structure(self):
        schema = write_todos_tool_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "write_todos"
        params = schema["function"]["parameters"]
        assert "todos" in params["properties"]


class TestPlanningMiddleware:
    @pytest.mark.asyncio
    async def test_before_injects_tool(self):
        mw = PlanningMiddleware()
        payload = await mw.before(ContextPayload())
        tool_names = [t["function"]["name"] for t in payload.tools]
        assert "write_todos" in tool_names

    @pytest.mark.asyncio
    async def test_before_injects_instruction(self):
        mw = PlanningMiddleware()
        payload = await mw.before(ContextPayload())
        assert any("write_todos" in s for s in payload.system_instructions)

    @pytest.mark.asyncio
    async def test_before_shows_plan_when_items_exist(self):
        todos = TodoList()
        todos.update([{"content": "step 1"}])
        mw = PlanningMiddleware(todos=todos)
        payload = await mw.before(ContextPayload())
        assert any("step 1" in s for s in payload.system_instructions)

    @pytest.mark.asyncio
    async def test_handle_write_todos(self):
        mw = PlanningMiddleware()
        result = await mw.handle_tool("write_todos", {
            "todos": [{"content": "do X"}, {"content": "do Y", "status": "done"}]
        })
        assert result is not None
        assert result.success
        assert "do X" in result.output
        assert mw.todos.progress == (1, 2)

    @pytest.mark.asyncio
    async def test_handle_ignores_other_tools(self):
        mw = PlanningMiddleware()
        result = await mw.handle_tool("read_file", {})
        assert result is None

    def test_name_and_priority(self):
        mw = PlanningMiddleware()
        assert mw.name == "planning"
        assert mw.priority == 30
