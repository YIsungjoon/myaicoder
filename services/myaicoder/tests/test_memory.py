"""Tests for Memory system (MemoryStore, AgentsmdLoader, MemoryMiddleware)."""

import json
import pytest

from myaicoder.core.memory.loader import AgentsmdLoader
from myaicoder.core.memory.store import MemoryStore
from myaicoder.core.middleware.base import ContextPayload
from myaicoder.core.middleware.memory import MemoryMiddleware


class TestMemoryStore:
    def test_save_and_recall(self, tmp_path):
        store = MemoryStore(storage_dir=tmp_path)
        store.save("project uses FastAPI", tags=["tech"])
        store.save("team prefers pytest")
        results = store.recall_recent(limit=10)
        assert len(results) == 2
        assert "FastAPI" in results[0]

    def test_search_by_content(self, tmp_path):
        store = MemoryStore(storage_dir=tmp_path)
        store.save("Python 3.12 is required")
        store.save("Use ruff for linting")
        results = store.search("Python")
        assert len(results) == 1
        assert "Python" in results[0]

    def test_search_by_tag(self, tmp_path):
        store = MemoryStore(storage_dir=tmp_path)
        store.save("use async everywhere", tags=["convention"])
        store.save("no global state", tags=["convention"])
        store.save("deploy to EKS", tags=["infra"])
        results = store.search("convention")
        assert len(results) == 2

    def test_search_empty_query_returns_recent(self, tmp_path):
        store = MemoryStore(storage_dir=tmp_path)
        store.save("item1")
        store.save("item2")
        results = store.search("")
        assert len(results) == 2

    def test_persistence_across_instances(self, tmp_path):
        store1 = MemoryStore(storage_dir=tmp_path)
        store1.save("persistent data")
        store2 = MemoryStore(storage_dir=tmp_path)
        assert store2.count == 1
        assert store2.recall_recent()[0] == "persistent data"

    def test_clear(self, tmp_path):
        store = MemoryStore(storage_dir=tmp_path)
        store.save("temp")
        store.clear()
        assert store.count == 0

    def test_corrupt_file_handled(self, tmp_path):
        (tmp_path / "memories.json").write_text("not json")
        store = MemoryStore(storage_dir=tmp_path)
        assert store.count == 0

    def test_count(self, tmp_path):
        store = MemoryStore(storage_dir=tmp_path)
        assert store.count == 0
        store.save("a")
        store.save("b")
        assert store.count == 2

    def test_to_openai_tools(self, tmp_path):
        store = MemoryStore(storage_dir=tmp_path)
        tools = store.to_openai_tools()
        assert len(tools) == 2
        names = {t["function"]["name"] for t in tools}
        assert names == {"save_memory", "recall_memory"}

    def test_atomic_write(self, tmp_path):
        store = MemoryStore(storage_dir=tmp_path)
        store.save("test")
        # No .tmp file should remain
        assert not (tmp_path / "memories.tmp").exists()
        # .json should exist and be valid
        data = json.loads((tmp_path / "memories.json").read_text())
        assert len(data) == 1


class TestAgentsmdLoader:
    def test_load_from_working_dir(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Be concise.")
        loader = AgentsmdLoader(working_dir=tmp_path)
        result = loader.load()
        assert result == "Be concise."

    def test_load_returns_none_when_missing(self, tmp_path):
        loader = AgentsmdLoader(working_dir=tmp_path)
        result = loader.load()
        assert result is None

    def test_load_skips_empty_file(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("")
        loader = AgentsmdLoader(working_dir=tmp_path)
        result = loader.load()
        assert result is None


class TestMemoryMiddleware:
    def _make_middleware(self, tmp_path, agents_md: str | None = None):
        store = MemoryStore(storage_dir=tmp_path / "memory")
        if agents_md:
            (tmp_path / "AGENTS.md").write_text(agents_md)
        loader = AgentsmdLoader(working_dir=tmp_path)
        return MemoryMiddleware(store=store, loader=loader), store

    @pytest.mark.asyncio
    async def test_before_injects_tools(self, tmp_path):
        mw, _ = self._make_middleware(tmp_path)
        payload = await mw.before(ContextPayload())
        tool_names = [t["function"]["name"] for t in payload.tools]
        assert "save_memory" in tool_names
        assert "recall_memory" in tool_names

    @pytest.mark.asyncio
    async def test_before_injects_agents_md(self, tmp_path):
        mw, _ = self._make_middleware(tmp_path, agents_md="Always use type hints.")
        payload = await mw.before(ContextPayload())
        assert any("type hints" in s for s in payload.system_instructions)

    @pytest.mark.asyncio
    async def test_before_injects_memories(self, tmp_path):
        mw, store = self._make_middleware(tmp_path)
        store.save("project uses Clean Architecture")
        payload = await mw.before(ContextPayload())
        assert any("Clean Architecture" in s for s in payload.system_instructions)

    @pytest.mark.asyncio
    async def test_handle_save_memory(self, tmp_path):
        mw, store = self._make_middleware(tmp_path)
        result = await mw.handle_tool("save_memory", {
            "content": "important fact", "tags": ["project"]
        })
        assert result is not None
        assert result.success
        assert store.count == 1

    @pytest.mark.asyncio
    async def test_handle_save_memory_empty_content(self, tmp_path):
        mw, _ = self._make_middleware(tmp_path)
        result = await mw.handle_tool("save_memory", {"content": ""})
        assert result is not None
        assert not result.success

    @pytest.mark.asyncio
    async def test_handle_recall_memory(self, tmp_path):
        mw, store = self._make_middleware(tmp_path)
        store.save("FastAPI is used")
        store.save("PostgreSQL for DB")
        result = await mw.handle_tool("recall_memory", {"query": "FastAPI"})
        assert result is not None
        assert result.success
        assert "FastAPI" in result.output

    @pytest.mark.asyncio
    async def test_handle_recall_no_results(self, tmp_path):
        mw, _ = self._make_middleware(tmp_path)
        result = await mw.handle_tool("recall_memory", {"query": "nothing"})
        assert result is not None
        assert "No matching" in result.output

    @pytest.mark.asyncio
    async def test_handle_ignores_other_tools(self, tmp_path):
        mw, _ = self._make_middleware(tmp_path)
        result = await mw.handle_tool("read_file", {})
        assert result is None

    def test_name_and_priority(self, tmp_path):
        mw, _ = self._make_middleware(tmp_path)
        assert mw.name == "memory"
        assert mw.priority == 20
