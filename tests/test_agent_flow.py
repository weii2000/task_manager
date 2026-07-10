import asyncio
from unittest.mock import AsyncMock

import pytest

from agent.flow import Flow
from agent.state import (
    Action,
    AgentDecision,
    Message,
    MessageRole,
    PlanningDraft,
    PlanningInfo,
    State,
)
from agent.tools.base import ToolContext
from exceptions.agent import AgentFlowStepLimitExceededError


def make_state() -> State:
    return State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
    )


def make_context() -> ToolContext:
    return ToolContext(user_id=1, db=AsyncMock())


def make_decision(content: str = "你的目标是什么？") -> AgentDecision:
    return AgentDecision(
        content=content,
        next_action=Action.CLARIFY,
        info=PlanningInfo(),
        draft=PlanningDraft(),
    )


def test_flow_stops_after_clarify():
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=make_decision())
    flow = Flow(provider=provider)

    result_state, response = asyncio.run(
        flow.run(make_state(), make_context())
    )

    assert result_state.messages[-1].content == "你的目标是什么？"
    assert result_state.next_action == Action.CLARIFY
    assert response == "你的目标是什么？"
    provider.complete.assert_awaited_once()


def test_flow_raises_when_step_limit_exceeded():
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=make_decision("继续澄清"))
    flow = Flow(provider=provider, max_steps=2)
    flow.clarify_node - Action.CLARIFY.value >> flow.clarify_node  # pyright: ignore[reportUnusedExpression]

    with pytest.raises(AgentFlowStepLimitExceededError):
        asyncio.run(flow.run(make_state(), make_context()))
