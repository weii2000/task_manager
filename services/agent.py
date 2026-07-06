from agent.flow import Flow
from agent.state import Message, MessageRole, PlanningDraft, PlanningInfo, State
from crud.agent import get_agent_session_by_session_id_and_user_id, save_agent_session, update_agent_session_by_session_id_and_user_id
from exceptions.agent import AgentSessionNotFoundError
from models.agent import AgentSession
from schemas.agent import AgentTurnRequest
from sqlalchemy.ext.asyncio import AsyncSession


async def create_agent_session_for_user(request: AgentTurnRequest, user_id: int, db: AsyncSession, flow: Flow) -> tuple[AgentSession, str]:
    messages = [Message(role=MessageRole.USER, content=request.message)]
    state = State(messages=messages, info=PlanningInfo(), draft=PlanningDraft())
    response_state, response = await flow.run(state)
    async with db.begin():
        agent_session = await save_agent_session(user_id, response_state.model_dump_json(), db)
    return agent_session, response


async def resume_agent_session_by_session_id_for_user(
        request: AgentTurnRequest, 
        session_id: int,
        user_id: int, 
        db: AsyncSession,
        flow: Flow
) -> tuple[AgentSession, str]:
    async with db.begin():
        agent_session = await get_agent_session_by_session_id_and_user_id(session_id, user_id, db)
    if not agent_session:
        raise AgentSessionNotFoundError()
    state = State.model_validate_json(agent_session.state_json)
    state.messages.append(Message(role=MessageRole.USER, content=request.message))
    response_state, response = await flow.run(state)
    async with db.begin():
        agent_session = await update_agent_session_by_session_id_and_user_id(session_id, user_id, response_state.model_dump_json(), db)
    if not agent_session:
        raise AgentSessionNotFoundError()
    return agent_session, response