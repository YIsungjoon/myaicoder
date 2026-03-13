"""Tests for AgentEngine."""

import pytest

from myaicoder.core.engine import AgentEngine


@pytest.mark.asyncio
async def test_chat_basic(mock_llm):
    engine = AgentEngine(llm=mock_llm)
    response = await engine.chat("Hello")

    assert response == "Hello! I'm a mock AI assistant."
    assert engine.conversation.message_count == 2  # user + assistant


@pytest.mark.asyncio
async def test_chat_stream(mock_llm):
    engine = AgentEngine(llm=mock_llm)
    chunks = []
    async for chunk in engine.chat_stream("Hello"):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert engine.conversation.message_count == 2


@pytest.mark.asyncio
async def test_reset(mock_llm):
    engine = AgentEngine(llm=mock_llm)
    await engine.chat("Hello")
    assert engine.conversation.message_count == 2

    engine.reset()
    assert engine.conversation.message_count == 0


@pytest.mark.asyncio
async def test_multi_turn(mock_llm_with_responses):
    llm = mock_llm_with_responses(["First response", "Second response"])
    engine = AgentEngine(llm=llm)

    r1 = await engine.chat("First question")
    assert r1 == "First response"

    r2 = await engine.chat("Second question")
    assert r2 == "Second response"

    assert engine.conversation.message_count == 4  # 2 user + 2 assistant
