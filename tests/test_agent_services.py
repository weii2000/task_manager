import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.state import (
    Action,
    AgentPhase,
    ExecutionResult,
    Message,
    MessageRole,
    PlanningDraft,
    PlanningInfo,
    PlanningProject,
    PlanningTask,
    State,
)
from agent.context import RetrievedMemory
from exceptions.agent import (
    AgentSessionNotAcceptingTurnError,
    AgentSessionNotAwaitingConfirmationError,
    AgentSessionNotFoundError,
    AgentSessionStateConflictError,
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


@pytest.fixture(autouse=True)
def mock_agent_memory_retrieval(monkeypatch):
    monkeypatch.setattr(
        agent_service,
        "get_active_memory_references_for_user",
        AsyncMock(return_value=[]),
    )


def test_create_session_loads_long_term_memories(monkeypatch):
    memory = RetrievedMemory(
        memory_id=8,
        category="preference",
        content="用户偏好一小时以内的任务",
    )
    get_memories = AsyncMock(return_value=[memory])
    monkeypatch.setattr(
        agent_service,
        "get_active_memory_references_for_user",
        get_memories,
    )
    db = make_db_with_transaction()
    flow = MagicMock()

    async def run_flow(state, context):
        assert context.retrieved_memories == (memory,)
        assert not hasattr(state, "long_term_memories")
        state.messages.append(
            Message(role=MessageRole.ASSISTANT, content="请补充目标")
        )
        return state, "请补充目标"

    flow.run = AsyncMock(side_effect=run_flow)
    session = SimpleNamespace(session_id=1, state_json="")

    async def save_session(user_id, state_json, save_db):
        assert user_id == 1
        assert save_db is db
        session.state_json = state_json
        return session

    monkeypatch.setattr(
        agent_service,
        "save_agent_session",
        AsyncMock(side_effect=save_session),
    )
    extract_pending = AsyncMock(return_value=[])
    monkeypatch.setattr(
        agent_service,
        "extract_pending_memories_from_turn",
        extract_pending,
    )
    extractor = object()

    returned_session, response = asyncio.run(
        agent_service.create_agent_session_for_user(
            AgentTurnRequest(message="帮我规划学习"),
            user_id=1,
            db=db,
            flow=flow,
            memory_extractor=extractor,
        )
    )

    assert returned_session is session
    assert response == "请补充目标"
    get_memories.assert_awaited_once_with(1, db)
    extraction_args = extract_pending.await_args.args
    assert [message.content for message in extraction_args[0]] == [
        "帮我规划学习"
    ]
    assert extraction_args[1:] == (0, 1, 1, db, extractor)


def test_memory_extraction_failure_does_not_fail_agent_turn(
    monkeypatch,
):
    extract_pending = AsyncMock(side_effect=RuntimeError("failed"))
    monkeypatch.setattr(
        agent_service,
        "extract_pending_memories_from_turn",
        extract_pending,
    )
    state = State(
        messages=[Message(role=MessageRole.USER, content="记住我的偏好")]
    )

    asyncio.run(
        agent_service._extract_memories_best_effort(
            state=state,
            user_id=1,
            session_id=2,
            db=make_db_with_transaction(),
            extractor=object(),
        )
    )

    extract_pending.assert_awaited_once()


def test_get_agent_session_returns_owned_session(monkeypatch):
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")]
    )
    agent_session = SimpleNamespace(
        session_id=7,
        state_json=state.model_dump_json(),
    )
    get_session = AsyncMock(return_value=agent_session)
    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        get_session,
    )
    db = make_db_with_transaction()

    result = asyncio.run(
        agent_service.get_agent_session_by_session_id_for_user(
            session_id=7,
            user_id=3,
            db=db,
        )
    )

    assert result is agent_session
    get_session.assert_awaited_once_with(7, 3, db)


def test_get_agent_session_not_found_raises(monkeypatch):
    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=None),
    )
    db = make_db_with_transaction()

    with pytest.raises(AgentSessionNotFoundError):
        asyncio.run(
            agent_service.get_agent_session_by_session_id_for_user(
                session_id=7,
                user_id=3,
                db=db,
            )
        )


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
        "get_agent_session_for_update",
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


def test_resume_rejects_stale_llm_result(monkeypatch):
    original_state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")]
    )
    original_session = SimpleNamespace(
        session_id=1,
        state_json=original_state.model_dump_json(),
    )
    executed_state = State(
        messages=[
            Message(role=MessageRole.USER, content="帮我规划学习"),
            Message(role=MessageRole.ASSISTANT, content="项目已创建"),
        ],
        phase=AgentPhase.COMPLETED,
        next_action=None,
        execution=ExecutionResult(
            project_id=42,
            project_title="学习计划",
            created_task_count=1,
            completed_at=datetime.now(timezone.utc),
        ),
    )
    locked_session = SimpleNamespace(
        session_id=1,
        state_json=executed_state.model_dump_json(),
    )
    db = make_db_with_transaction()
    flow = MagicMock()
    flow.run = AsyncMock(return_value=(original_state, "规划完成"))
    update_session = AsyncMock()

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_by_session_id_and_user_id",
        AsyncMock(return_value=original_session),
    )
    monkeypatch.setattr(
        agent_service,
        "get_agent_session_for_update",
        AsyncMock(return_value=locked_session),
    )
    monkeypatch.setattr(
        agent_service,
        "update_agent_session_state",
        update_session,
    )

    with pytest.raises(AgentSessionStateConflictError):
        asyncio.run(
            agent_service.resume_agent_session_by_session_id_for_user(
                AgentTurnRequest(message="继续规划"),
                session_id=1,
                user_id=1,
                db=db,
                flow=flow,
            )
        )

    update_session.assert_not_awaited()


def test_resume_rejects_message_while_awaiting_confirmation(monkeypatch):
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        phase=AgentPhase.CONFIRMING,
        next_action=None,
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


def test_confirm_approved_executes_plan(monkeypatch):
    state = State(
        messages=[
            Message(role=MessageRole.USER, content="帮我规划学习"),
            Message(role=MessageRole.ASSISTANT, content="请确认计划"),
        ],
        phase=AgentPhase.CONFIRMING,
        next_action=None,
        draft=PlanningDraft(
            project=PlanningProject(title="学习计划"),
            tasks=[PlanningTask(title="完成第一阶段学习")],
        ),
    )
    agent_session = SimpleNamespace(
        session_id=1,
        state_json=state.model_dump_json(),
    )
    db = make_db_with_transaction()
    flow = MagicMock()
    execution = ExecutionResult(
        project_id=42,
        project_title="学习计划",
        created_task_count=1,
        completed_at=datetime.now(timezone.utc),
    )

    async def run_flow(execution_state, context):
        assert context.user_id == 1
        assert context.session_id == agent_session.session_id
        assert execution_state.phase == AgentPhase.EXECUTING
        assert execution_state.next_action == Action.EXECUTE
        execution_state.phase = AgentPhase.COMPLETED
        execution_state.next_action = None
        execution_state.execution = execution
        execution_state.messages.append(
            Message(role=MessageRole.ASSISTANT, content="项目已创建")
        )
        return execution_state, "项目已创建"

    flow.run = AsyncMock(side_effect=run_flow)

    async def update_session(
        locked_session,
        new_state_json,
        update_db,
    ):
        assert locked_session is agent_session
        assert update_db is db
        agent_session.state_json = new_state_json
        return agent_session

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_for_update",
        AsyncMock(return_value=agent_session),
    )
    monkeypatch.setattr(
        agent_service,
        "update_agent_session_state",
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
    assert updated_state.phase == AgentPhase.COMPLETED
    assert updated_state.next_action is None
    assert updated_state.human_decision is not None
    assert updated_state.human_decision.approved is True
    assert updated_state.execution == execution
    assert response == "项目已创建"
    flow.run.assert_awaited_once()


def test_confirm_rejected_replans_with_feedback(monkeypatch):
    state = State(
        messages=[
            Message(role=MessageRole.USER, content="帮我规划学习"),
            Message(role=MessageRole.ASSISTANT, content="请确认计划"),
        ],
        phase=AgentPhase.CONFIRMING,
        next_action=None,
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
        locked_session,
        new_state_json,
        update_db,
    ):
        assert locked_session is agent_session
        agent_session.state_json = new_state_json
        return agent_session

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_for_update",
        AsyncMock(return_value=agent_session),
    )
    monkeypatch.setattr(
        agent_service,
        "update_agent_session_state",
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


def test_repeated_approval_returns_existing_execution(monkeypatch):
    execution = ExecutionResult(
        project_id=42,
        project_title="学习计划",
        created_task_count=1,
        completed_at=datetime.now(timezone.utc),
    )
    state = State(
        messages=[
            Message(role=MessageRole.USER, content="帮我规划学习"),
            Message(role=MessageRole.ASSISTANT, content="项目已创建"),
        ],
        phase=AgentPhase.COMPLETED,
        next_action=None,
        execution=execution,
    )
    agent_session = SimpleNamespace(
        session_id=1,
        state_json=state.model_dump_json(),
    )
    db = make_db_with_transaction()
    flow = MagicMock()
    flow.run = AsyncMock()
    update_session = AsyncMock()

    monkeypatch.setattr(
        agent_service,
        "get_agent_session_for_update",
        AsyncMock(return_value=agent_session),
    )
    monkeypatch.setattr(
        agent_service,
        "update_agent_session_state",
        update_session,
    )

    returned_session, response = asyncio.run(
        agent_service.confirm_agent_session_for_user(
            AgentConfirmRequest(approved=True),
            session_id=agent_session.session_id,
            user_id=1,
            db=db,
            flow=flow,
        )
    )

    assert returned_session is agent_session
    assert response == "项目已创建"
    flow.run.assert_not_awaited()
    update_session.assert_not_awaited()


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
        "get_agent_session_for_update",
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
