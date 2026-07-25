import logging

from sqlalchemy.ext.asyncio import AsyncSession

from agent.memory.extraction import MemoryExtractor
from agent.runtime.context import AgentRunContext
from agent.runtime.flow import Flow
from agent.runtime.state import (
    Action,
    AgentPhase,
    HumanDecision,
    Message,
    MessageRole,
    State,
)
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
from services.memory import (
    extract_pending_memories_from_turn,
    get_active_memory_references_for_user,
)

logger = logging.getLogger(__name__)


async def create_agent_session_for_user(
    request: AgentTurnRequest,
    user_id: int,
    db: AsyncSession,
    flow: Flow,
    memory_extractor: MemoryExtractor | None = None,
) -> tuple[AgentSession, str]:
    state = State(
        messages=[
            Message(role=MessageRole.USER, content=request.message)
        ]
    )
    async with db.begin():
        memories = await get_active_memory_references_for_user(
            user_id,
            db,
        )
    context = AgentRunContext(
        user_id=user_id,
        db=db,
        retrieved_memories=tuple(memories),
    )
    response_state, response = await flow.run(state, context)
    async with db.begin():
        agent_session = await save_agent_session(
            user_id,
            response_state.model_dump_json(),
            db,
        )
    await _extract_memories_best_effort(
        response_state,
        user_id,
        agent_session.session_id,
        db,
        memory_extractor,
    )
    return agent_session, response


async def get_agent_session_by_session_id_for_user(
    session_id: int,
    user_id: int,
    db: AsyncSession,
) -> AgentSession:
    async with db.begin():
        agent_session = (
            await get_agent_session_by_session_id_and_user_id(
                session_id,
                user_id,
                db,
            )
        )

    if agent_session is None:
        raise AgentSessionNotFoundError()

    return agent_session


async def resume_agent_session_by_session_id_for_user(
    request: AgentTurnRequest,
    session_id: int,
    user_id: int,
    db: AsyncSession,
    flow: Flow,
    memory_extractor: MemoryExtractor | None = None,
) -> tuple[AgentSession, str]:
    async with db.begin():
        agent_session = await get_agent_session_by_session_id_and_user_id(
            session_id,
            user_id,
            db,
        )
        memories = (
            await get_active_memory_references_for_user(user_id, db)
            if agent_session is not None
            else []
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
    context = AgentRunContext(
        user_id=user_id,
        db=db,
        session_id=session_id,
        retrieved_memories=tuple(memories),
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

    await _extract_memories_best_effort(
        response_state,
        user_id,
        session_id,
        db,
        memory_extractor,
    )
    return updated_session, response


async def confirm_agent_session_for_user(
    request: AgentConfirmRequest,
    session_id: int,
    user_id: int,
    db: AsyncSession,
    flow: Flow,
    memory_extractor: MemoryExtractor | None = None,
) -> tuple[AgentSession, str]:
    if not request.approved:
        return await _reject_agent_session_for_user(
            request,
            session_id,
            user_id,
            db,
            flow,
            memory_extractor,
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
        if state.phase == AgentPhase.COMPLETED:
            return agent_session, state.messages[-1].content
        if state.phase != AgentPhase.CONFIRMING:
            raise AgentSessionNotAwaitingConfirmationError()

        state.human_decision = HumanDecision.model_validate(
            request.model_dump()
        )
        state.phase = AgentPhase.EXECUTING
        state.next_action = Action.EXECUTE
        context = AgentRunContext(
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
    memory_extractor: MemoryExtractor | None = None,
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
        if state.phase != AgentPhase.CONFIRMING:
            raise AgentSessionNotAwaitingConfirmationError()
        memories = await get_active_memory_references_for_user(
            user_id,
            db,
        )

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
    context = AgentRunContext(
        user_id=user_id,
        db=db,
        session_id=session_id,
        retrieved_memories=tuple(memories),
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

    await _extract_memories_best_effort(
        response_state,
        user_id,
        session_id,
        db,
        memory_extractor,
    )
    return updated_session, response


async def _extract_memories_best_effort(
    state: State,
    user_id: int,
    session_id: int,
    db: AsyncSession,
    extractor: MemoryExtractor | None,
) -> None:
    if extractor is None:
        return

    latest_user_index = next(
        (
            index
            for index in range(len(state.messages) - 1, -1, -1)
            if state.messages[index].role == MessageRole.USER
        ),
        None,
    )
    if latest_user_index is None:
        return

    window_start = max(0, latest_user_index - 3)
    messages = state.messages[window_start : latest_user_index + 1]
    try:
        await extract_pending_memories_from_turn(
            messages,
            latest_user_index,
            session_id,
            user_id,
            db,
            extractor,
        )
    except Exception:
        logger.exception(
            "Long-term memory extraction failed for user=%s session=%s",
            user_id,
            session_id,
        )
