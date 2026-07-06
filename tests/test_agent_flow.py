import asyncio
from unittest.mock import AsyncMock

import pytest

from agent.flow import Flow
from agent.state import Action, Message, MessageRole, PlanningDraft, PlanningInfo, ResponseMessage, State
from exceptions.agent import AgentFlowStepLimitExceededError


def make_state() -> State:
    return State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        info=PlanningInfo(),
        draft=PlanningDraft(),
    )


def test_flow_stops_after_clarify():
    provider = AsyncMock()
    response_state = make_state()
    response_state.messages.append(
        ResponseMessage(
            role=MessageRole.ASSISTANT,
            content="你的目标是什么？",
            next_action=Action.CLARIFY,
        )
    )
    provider.complete = AsyncMock(return_value=response_state)
    flow = Flow(provider=provider)

    result_state, response = asyncio.run(flow.run(make_state()))

    assert result_state is response_state
    assert response == "你的目标是什么？"
    provider.complete.assert_awaited_once()


def test_flow_raises_when_step_limit_exceeded():
    provider = AsyncMock()
    response_state = make_state()
    response_state.messages.append(
        ResponseMessage(
            role=MessageRole.ASSISTANT,
            content="继续澄清",
            next_action=Action.CLARIFY,
        )
    )
    provider.complete = AsyncMock(return_value=response_state)
    flow = Flow(provider=provider, max_steps=2)
    flow.clarify_node - Action.CLARIFY.value >> flow.clarify_node  # pyright: ignore[reportUnusedExpression]

    with pytest.raises(AgentFlowStepLimitExceededError):
        asyncio.run(flow.run(make_state()))
