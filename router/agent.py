from fastapi import APIRouter, Depends
from models.user import User

from agent.provider import PlanningProvider
from agent.state import PlanningState
from dependencies.agent import get_planning_provider
from dependencies.auth import get_current_user
from schemas.agent import PlanningTurnRequest
from schemas.response import ApiResponse
from services.agent import run_planning_turn_for_user


router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
)


@router.post(
    "/planning/turn",
    response_model=ApiResponse[PlanningState],
)
async def run_planning_turn_api(
    turn_request: PlanningTurnRequest,
    current_user: User = Depends(get_current_user),
    provider: PlanningProvider = Depends(
        get_planning_provider
    ),
):
    state = await run_planning_turn_for_user(
        turn_request,
        provider,
    )

    return ApiResponse[PlanningState](
        message="规划处理成功",
        data=state,
    )
