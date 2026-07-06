import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.state import Message, MessageRole, PlanningDraft, PlanningInfo, State
from exceptions.agent import AgentSessionNotFoundError
from schemas.agent import AgentTurnRequest
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
