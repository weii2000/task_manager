from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import AgentSession


async def save_agent_session(user_id: int, state_json: str, db: AsyncSession) -> AgentSession:
    agent_session = AgentSession(user_id=user_id, state_json=state_json)
    db.add(agent_session)
    await db.flush()
    await db.refresh(agent_session)
    return agent_session


async def get_agent_session_by_session_id_and_user_id(session_id: int, user_id: int, db: AsyncSession) -> AgentSession | None:
    agent_session = await db.execute(
        select(AgentSession).where(
            AgentSession.user_id == user_id,
            AgentSession.session_id == session_id,
        )
    )
    return agent_session.scalar_one_or_none()


async def get_agent_session_for_update(
    session_id: int,
    user_id: int,
    db: AsyncSession,
) -> AgentSession | None:
    result = await db.execute(
        select(AgentSession)
        .where(
            AgentSession.user_id == user_id,
            AgentSession.session_id == session_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def update_agent_session_state(
    agent_session: AgentSession,
    new_state_json: str,
    db: AsyncSession,
) -> AgentSession:
    agent_session.state_json = new_state_json
    await db.flush()
    await db.refresh(agent_session)
    return agent_session


async def update_agent_session_by_session_id_and_user_id(
        session_id: int, 
        user_id: int, 
        new_state_json: str, 
        db: AsyncSession,
) -> AgentSession | None:
    agent_session = await get_agent_session_by_session_id_and_user_id(session_id, user_id, db)
    if not agent_session:
        return None
    agent_session.state_json = new_state_json
    await db.flush()
    await db.refresh(agent_session)
    return agent_session


async def delete_agent_session_by_session_id_and_user_id(
        session_id: int, 
        user_id: int, 
        db: AsyncSession,
) -> bool:
    agent_session = await get_agent_session_by_session_id_and_user_id(
        session_id,
        user_id,
        db,
    )
    if agent_session is None:
        return False

    await db.delete(agent_session)
    await db.flush()
    return True
