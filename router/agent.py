from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent.flow import Flow
from agent.state import State
from database.session import get_db
from dependencies.agent import get_agent_flow
from dependencies.auth import get_current_user
from models.user import User
from schemas.agent import AgentSessionRead, AgentTurnRequest, ClarificationResponse
from schemas.response import ApiResponse
from services.agent import create_agent_session_for_user, resume_agent_session_by_session_id_for_user


router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/", response_model=ApiResponse[ClarificationResponse])
async def create_agent_session_for_user_api(
    request: AgentTurnRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    flow: Flow = Depends(get_agent_flow)
):
    agent_session, response = await create_agent_session_for_user(request, current_user.user_id, db, flow)
    return ApiResponse[ClarificationResponse](
        data=ClarificationResponse(
            session=AgentSessionRead(
                session_id=agent_session.session_id,
                state=State.model_validate_json(agent_session.state_json),
            ), response=response)
    )


@router.patch("/", response_model=ApiResponse[ClarificationResponse])
async def resume_agent_session_by_session_id_for_user_api(
    request: AgentTurnRequest,
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    flow: Flow = Depends(get_agent_flow)
):
    agent_session, response = await resume_agent_session_by_session_id_for_user(request, session_id, current_user.user_id, db, flow)
    return ApiResponse[ClarificationResponse](
        data=ClarificationResponse(
            session=AgentSessionRead(
                session_id=agent_session.session_id,
                state=State.model_validate_json(agent_session.state_json),
            ), response=response)
    )