from sqlalchemy.ext.asyncio import AsyncSession

from agent.flow import Flow
from agent.state import (
    Action,
    AgentPhase,
    HumanDecision,
    Message,
    MessageRole,
    State,
)
from agent.tools.base import ToolContext
from crud.agent import (
    get_agent_session_by_session_id_and_user_id,
    get_agent_session_for_update,
    save_agent_session,
    update_agent_session_state,
)
from exceptions.agent import (
    AgentSessionNotAcceptingTurnError,
    AgentSessionNotAwaitingConfirmationError,
    AgentSessionNotFoundError,
    AgentSessionStateConflictError,
)
from models.agent import AgentSession
from schemas.agent import AgentConfirmRequest, AgentTurnRequest


async def create_agent_session_for_user(
    request: AgentTurnRequest,
    user_id: int,
    db: AsyncSession,
    flow: Flow,
) -> tuple[AgentSession, str]:
    state = State(
        messages=[
            Message(role=MessageRole.USER, content=request.message)
        ]
    )
    context = ToolContext(user_id, db)
    response_state, response = await flow.run(state, context)
    async with db.begin():
        agent_session = await save_agent_session(
            user_id,
            response_state.model_dump_json(),
            db,
        )
    return agent_session, response


async def resume_agent_session_by_session_id_for_user(
    request: AgentTurnRequest,
    session_id: int,
    user_id: int,
    db: AsyncSession,
    flow: Flow,
) -> tuple[AgentSession, str]:
    async with db.begin():
        agent_session = await get_agent_session_by_session_id_and_user_id(
            session_id,
            user_id,
            db,
        )
    if agent_session is None:
        raise AgentSessionNotFoundError()

    original_state_json = agent_session.state_json
    state = State.model_validate_json(original_state_json)
    if state.phase != AgentPhase.PLANNING:
        raise AgentSessionNotAcceptingTurnError()

    state.messages.append(
        Message(role=MessageRole.USER, content=request.message)
    )
    state.next_action = Action.PLAN
    state.pending_tool_calls = []
    context = ToolContext(user_id, db)
    response_state, response = await flow.run(state, context)
    async with db.begin():
        locked_session = await get_agent_session_for_update(
            session_id,
            user_id,
            db,
        )
        if locked_session is None:
            raise AgentSessionNotFoundError()
        if locked_session.state_json != original_state_json:
            raise AgentSessionStateConflictError()
        updated_session = await update_agent_session_state(
            locked_session,
            response_state.model_dump_json(),
            db,
        )

    return updated_session, response


async def confirm_agent_session_for_user(
    request: AgentConfirmRequest,
    session_id: int,
    user_id: int,
    db: AsyncSession,
    flow: Flow,
) -> tuple[AgentSession, str]:
    if not request.approved:
        return await _reject_agent_session_for_user(
            request,
            session_id,
            user_id,
            db,
            flow,
        )

    async with db.begin():
        agent_session = await get_agent_session_for_update(
            session_id,
            user_id,
            db,
        )
        if agent_session is None:
            raise AgentSessionNotFoundError()

        state = State.model_validate_json(agent_session.state_json)
        if state.phase == AgentPhase.EXECUTED:
            return agent_session, state.messages[-1].content
        if state.phase != AgentPhase.AWAITING_CONFIRMATION:
            raise AgentSessionNotAwaitingConfirmationError()

        state.human_decision = HumanDecision.model_validate(
            request.model_dump()
        )
        state.phase = AgentPhase.READY_TO_EXECUTE
        state.next_action = Action.EXECUTE
        context = ToolContext(
            user_id=user_id,
            db=db,
            session_id=session_id,
        )
        response_state, response = await flow.run(state, context)

        updated_session = await update_agent_session_state(
            agent_session,
            response_state.model_dump_json(),
            db,
        )

    return updated_session, response


async def _reject_agent_session_for_user(
    request: AgentConfirmRequest,
    session_id: int,
    user_id: int,
    db: AsyncSession,
    flow: Flow,
) -> tuple[AgentSession, str]:
    async with db.begin():
        agent_session = await get_agent_session_for_update(
            session_id,
            user_id,
            db,
        )
        if agent_session is None:
            raise AgentSessionNotFoundError()

        original_state_json = agent_session.state_json
        state = State.model_validate_json(original_state_json)
        if state.phase != AgentPhase.AWAITING_CONFIRMATION:
            raise AgentSessionNotAwaitingConfirmationError()

    state.human_decision = HumanDecision.model_validate(
        request.model_dump()
    )
    feedback = (request.feedback or "").strip()
    state.messages.append(
        Message(role=MessageRole.USER, content=feedback)
    )
    state.phase = AgentPhase.PLANNING
    state.next_action = Action.PLAN
    state.pending_tool_calls = []
    state.revision_count += 1
    context = ToolContext(
        user_id=user_id,
        db=db,
        session_id=session_id,
    )
    response_state, response = await flow.run(state, context)

    async with db.begin():
        locked_session = await get_agent_session_for_update(
            session_id,
            user_id,
            db,
        )
        if locked_session is None:
            raise AgentSessionNotFoundError()
        if locked_session.state_json != original_state_json:
            raise AgentSessionStateConflictError()
        updated_session = await update_agent_session_state(
            locked_session,
            response_state.model_dump_json(),
            db,
        )

    return updated_session, response
