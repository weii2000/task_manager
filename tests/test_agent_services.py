import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.state import (
    Action,
    AgentPhase,
    Message,
    MessageRole,
    PlanningDraft,
    PlanningInfo,
    State,
)
from exceptions.agent import (
    AgentSessionNotAcceptingTurnError,
    AgentSessionNotAwaitingConfirmationError,
    AgentSessionNotFoundError,
)
from schemas.agent import AgentConfirmRequest, AgentTurnRequest
from services import agent as agent_service


def make_db_with_transaction():
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    db = MagicMock()
    db.begin.return_value = transaction
    return db


def test_resume_agent_session_not_found_raises(monkeypatch):
    db = make_db_with_transaction()
    flow = MagicMock()
    flow.run = AsyncMock()

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=None),
    )

    with pytest.raises(AgentSessionNotFoundError):
        asyncio.run(
            agent_service.resume_agent_session_by_session_id_for_user(
                AgentTurnRequest(message="继续规划"),
                session_id=1,
                user_id=1,
                db=db,
                flow=flow,
            )
        )

    flow.run.assert_not_awaited()


def test_resume_agent_session_update_not_found_raises(monkeypatch):
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        info=PlanningInfo(),
        draft=PlanningDraft(),
    )
    agent_session = SimpleNamespace(
        session_id=1,
        state_json=state.model_dump_json(),
    )
    db = make_db_with_transaction()
    flow = MagicMock()
    flow.run = AsyncMock(return_value=(state, "好的"))

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=agent_session),
    )
    monkeypatch.setattr(
        agent_service,
        "update_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=None),
    )

    with pytest.raises(AgentSessionNotFoundError):
        asyncio.run(
            agent_service.resume_agent_session_by_session_id_for_user(
                AgentTurnRequest(message="继续规划"),
                session_id=agent_session.session_id,
                user_id=1,
                db=db,
                flow=flow,
            )
        )

    flow.run.assert_awaited_once()


def test_resume_rejects_message_while_awaiting_confirmation(monkeypatch):
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        phase=AgentPhase.AWAITING_CONFIRMATION,
        next_action=Action.PAUSE,
    )
    agent_session = SimpleNamespace(
        session_id=1,
        state_json=state.model_dump_json(),
    )
    db = make_db_with_transaction()
    flow = MagicMock()
    flow.run = AsyncMock()

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=agent_session),
    )

    with pytest.raises(AgentSessionNotAcceptingTurnError):
        asyncio.run(
            agent_service.resume_agent_session_by_session_id_for_user(
                AgentTurnRequest(message="我同意"),
                session_id=agent_session.session_id,
                user_id=1,
                db=db,
                flow=flow,
            )
        )

    flow.run.assert_not_awaited()


def test_confirm_approved_marks_session_ready_to_execute(monkeypatch):
    state = State(
        messages=[
            Message(role=MessageRole.USER, content="帮我规划学习"),
            Message(role=MessageRole.ASSISTANT, content="请确认计划"),
        ],
        phase=AgentPhase.AWAITING_CONFIRMATION,
        next_action=Action.PAUSE,
    )
    agent_session = SimpleNamespace(
        session_id=1,
        state_json=state.model_dump_json(),
    )
    db = make_db_with_transaction()
    flow = MagicMock()
    flow.run = AsyncMock()

    async def update_session(
        session_id,
        user_id,
        new_state_json,
        update_db,
    ):
        assert session_id == agent_session.session_id
        assert user_id == 1
        assert update_db is db
        agent_session.state_json = new_state_json
        return agent_session

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=agent_session),
    )
    monkeypatch.setattr(
        agent_service,
        "update_agent_session_by_session_id_and_user_id",
        update_session,
    )

    updated_session, response = asyncio.run(
        agent_service.confirm_agent_session_for_user(
            AgentConfirmRequest(approved=True),
            session_id=agent_session.session_id,
            user_id=1,
            db=db,
            flow=flow,
        )
    )

    updated_state = State.model_validate_json(updated_session.state_json)
    assert updated_state.phase == AgentPhase.READY_TO_EXECUTE
    assert updated_state.next_action == Action.READY_TO_EXECUTE
    assert updated_state.human_decision is not None
    assert updated_state.human_decision.approved is True
    assert "待执行状态" in response
    flow.run.assert_not_awaited()


def test_confirm_rejected_replans_with_feedback(monkeypatch):
    state = State(
        messages=[
            Message(role=MessageRole.USER, content="帮我规划学习"),
            Message(role=MessageRole.ASSISTANT, content="请确认计划"),
        ],
        phase=AgentPhase.AWAITING_CONFIRMATION,
        next_action=Action.PAUSE,
    )
    agent_session = SimpleNamespace(
        session_id=1,
        state_json=state.model_dump_json(),
    )
    db = make_db_with_transaction()
    flow = MagicMock()

    async def run_flow(replan_state, context):
        assert context.user_id == 1
        assert replan_state.phase == AgentPhase.PLANNING
        assert replan_state.next_action == Action.PLAN
        assert replan_state.messages[-1].content == "任务粒度太粗"
        replan_state.messages.append(
            Message(role=MessageRole.ASSISTANT, content="已重新规划")
        )
        return replan_state, "已重新规划"

    flow.run = AsyncMock(side_effect=run_flow)

    async def update_session(
        session_id,
        user_id,
        new_state_json,
        update_db,
    ):
        agent_session.state_json = new_state_json
        return agent_session

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=agent_session),
    )
    monkeypatch.setattr(
        agent_service,
        "update_agent_session_by_session_id_and_user_id",
        update_session,
    )

    updated_session, response = asyncio.run(
        agent_service.confirm_agent_session_for_user(
            AgentConfirmRequest(
                approved=False,
                feedback="任务粒度太粗",
            ),
            session_id=agent_session.session_id,
            user_id=1,
            db=db,
            flow=flow,
        )
    )

    updated_state = State.model_validate_json(updated_session.state_json)
    assert response == "已重新规划"
    assert updated_state.revision_count == 1
    flow.run.assert_awaited_once()


def test_confirm_requires_awaiting_confirmation_phase(monkeypatch):
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")]
    )
    agent_session = SimpleNamespace(
        session_id=1,
        state_json=state.model_dump_json(),
    )
    db = make_db_with_transaction()
    flow = MagicMock()
    flow.run = AsyncMock()

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=agent_session),
    )

    with pytest.raises(AgentSessionNotAwaitingConfirmationError):
        asyncio.run(
            agent_service.confirm_agent_session_for_user(
                AgentConfirmRequest(approved=True),
                session_id=agent_session.session_id,
                user_id=1,
                db=db,
                flow=flow,
            )
        )
