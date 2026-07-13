from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent.flow import Flow
from agent.memory_extractor import MemoryExtractor
from agent.state import State
from database.session import get_db
from dependencies.agent import get_agent_flow, get_memory_extractor
from dependencies.auth import get_current_user
from models.agent import AgentSession
from models.user import User
from schemas.agent import (
    AgentConfirmRequest,
    AgentSessionRead,
    AgentTurnRequest,
    AgentTurnResponse,
)
from schemas.response import ApiResponse
from services.agent import (
    confirm_agent_session_for_user,
    create_agent_session_for_user,
    resume_agent_session_by_session_id_for_user,
)


router = APIRouter(prefix="/api/agent", tags=["agent"])


def build_agent_response(
    agent_session: AgentSession,
    response: str,
) -> ApiResponse[AgentTurnResponse]:
    return ApiResponse[AgentTurnResponse](
        data=AgentTurnResponse(
            session=AgentSessionRead(
                session_id=agent_session.session_id,
                state=State.model_validate_json(agent_session.state_json),
            ),
            response=response,
        )
    )


@router.post("/", response_model=ApiResponse[AgentTurnResponse])
async def create_agent_session_for_user_api(
    request: AgentTurnRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    flow: Flow = Depends(get_agent_flow),
    memory_extractor: MemoryExtractor = Depends(get_memory_extractor),
) -> ApiResponse[AgentTurnResponse]:
    agent_session, response = await create_agent_session_for_user(
        request,
        current_user.user_id,
        db,
        flow,
        memory_extractor,
    )
    return build_agent_response(agent_session, response)


@router.patch("/", response_model=ApiResponse[AgentTurnResponse])
async def resume_agent_session_by_session_id_for_user_api(
    request: AgentTurnRequest,
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    flow: Flow = Depends(get_agent_flow),
    memory_extractor: MemoryExtractor = Depends(get_memory_extractor),
) -> ApiResponse[AgentTurnResponse]:
    agent_session, response = (
        await resume_agent_session_by_session_id_for_user(
            request,
            session_id,
            current_user.user_id,
            db,
            flow,
            memory_extractor,
        )
    )
    return build_agent_response(agent_session, response)


@router.post(
    "/{session_id}/confirmation",
    response_model=ApiResponse[AgentTurnResponse],
)
async def confirm_agent_session_for_user_api(
    session_id: int,
    request: AgentConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    flow: Flow = Depends(get_agent_flow),
    memory_extractor: MemoryExtractor = Depends(get_memory_extractor),
) -> ApiResponse[AgentTurnResponse]:
    agent_session, response = await confirm_agent_session_for_user(
        request,
        session_id,
        current_user.user_id,
        db,
        flow,
        memory_extractor,
    )
    return build_agent_response(agent_session, response)
