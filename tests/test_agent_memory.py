import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from agent.memory import MemoryManager, MemorySummaryResult
from agent.prompt import PlanPromptBuilder
from agent.state import Message, MessageRole, State
from exceptions.agent import AgentProviderError


def make_messages(contents: list[str]) -> list[Message]:
    return [
        Message(role=MessageRole.USER, content=content)
        for content in contents
    ]


def make_manager(
    provider: AsyncMock,
    *,
    compact_threshold_chars: int = 20,
    recent_context_budget_chars: int = 15,
    max_recent_messages: int = 2,
) -> MemoryManager:
    return MemoryManager(
        provider=provider,
        compact_threshold_chars=compact_threshold_chars,
        recent_context_budget_chars=recent_context_budget_chars,
        max_recent_messages=max_recent_messages,
    )


def test_memory_does_not_compact_below_threshold():
    provider = AsyncMock()
    manager = make_manager(provider)
    state = State(messages=make_messages(["short message"]))

    result = asyncio.run(manager.compact(state))

    assert result is state
    provider.complete.assert_not_awaited()


def test_memory_compacts_prefix_with_count_and_character_limits():
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=MemorySummaryResult(summary="合并后的摘要")
    )
    manager = make_manager(
        provider,
        compact_threshold_chars=30,
        recent_context_budget_chars=28,
    )
    contents = [
        "old-goal",
        "old-answer",
        "recent-question",
        "latest-answer",
    ]
    state = State(messages=make_messages(contents))

    result = asyncio.run(manager.compact(state))

    assert result.memory_summary == "合并后的摘要"
    assert result.summarized_message_count == 2
    assert state.memory_summary is None
    assert state.summarized_message_count == 0

    request = provider.complete.await_args.args[0]
    payload = json.loads(request.messages[1].content)
    assert payload["previous_summary"] is None
    assert [message["content"] for message in payload["messages"]] == (
        contents[:2]
    )


def test_memory_character_budget_can_keep_fewer_recent_messages():
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=MemorySummaryResult(summary="压缩摘要")
    )
    manager = make_manager(
        provider,
        compact_threshold_chars=30,
        recent_context_budget_chars=15,
        max_recent_messages=8,
    )
    contents = ["a" * 10, "b" * 10, "c" * 10, "d" * 10]
    state = State(messages=make_messages(contents))

    result = asyncio.run(manager.compact(state))

    assert result.summarized_message_count == 3
    request = provider.complete.await_args.args[0]
    payload = json.loads(request.messages[1].content)
    assert [message["content"] for message in payload["messages"]] == (
        contents[:3]
    )


def test_memory_incrementally_merges_previous_summary():
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=MemorySummaryResult(summary="更新后的完整摘要")
    )
    manager = make_manager(
        provider,
        compact_threshold_chars=15,
        recent_context_budget_chars=12,
        max_recent_messages=1,
    )
    contents = [
        "old-one",
        "old-two",
        "new-three",
        "new-four",
        "new-five",
    ]
    state = State(
        messages=make_messages(contents),
        memory_summary="之前的摘要",
        summarized_message_count=2,
    )

    result = asyncio.run(manager.compact(state))

    assert result.memory_summary == "更新后的完整摘要"
    assert result.summarized_message_count == 4

    request = provider.complete.await_args.args[0]
    payload = json.loads(request.messages[1].content)
    assert payload["previous_summary"] == "之前的摘要"
    assert [message["content"] for message in payload["messages"]] == (
        contents[2:4]
    )


def test_memory_failure_does_not_mutate_state():
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=AgentProviderError())
    manager = make_manager(provider)
    state = State(
        messages=make_messages(
            ["first-long-message", "second-long-message"]
        )
    )
    original_state_json = state.model_dump_json()

    with pytest.raises(AgentProviderError):
        asyncio.run(manager.compact(state))

    assert state.model_dump_json() == original_state_json


def test_prompt_uses_summary_and_only_unsummarized_messages():
    state = State(
        messages=make_messages(
            ["summarized-one", "summarized-two", "recent-message"]
        ),
        memory_summary="历史摘要",
        summarized_message_count=2,
    )

    request = PlanPromptBuilder(frozenset()).build(state)
    context = json.loads(request.messages[1].content)["current_context"]

    assert context["memory_summary"] == "历史摘要"
    assert [message.content for message in request.messages[2:]] == [
        "recent-message"
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"compact_threshold_chars": 0},
        {"recent_context_budget_chars": 0},
        {
            "compact_threshold_chars": 10,
            "recent_context_budget_chars": 10,
        },
        {"max_recent_messages": 0},
    ],
)
def test_memory_rejects_invalid_configuration(kwargs: dict[str, int]):
    with pytest.raises(ValueError):
        MemoryManager(AsyncMock(), **kwargs)


def test_state_rejects_summary_without_summarized_messages():
    with pytest.raises(ValidationError):
        State(
            messages=make_messages(["new message"]),
            memory_summary="orphan summary",
        )
