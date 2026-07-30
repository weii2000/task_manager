from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from dependencies.auth import get_current_user
from models.user import User
from schemas.plan import (
    PlanCreate,
    PlanRead,
    PlanStatusUpdate,
    PlanUpdate,
)
from schemas.response import ApiResponse
from services.plan import (
    archive_plan_for_user,
    create_plan_for_user,
    get_plan_for_user,
    get_plans_for_user,
    restore_plan_for_user,
    update_plan_for_user,
    update_plan_status_for_user,
)

router = APIRouter(
    prefix="/api/plans",
    tags=["plans"],
)


@router.post(
    "",
    response_model=ApiResponse[PlanRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_plan_api(
    plan_create: PlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await create_plan_for_user(
        plan_create,
        current_user.user_id,
        db,
    )
    return ApiResponse[PlanRead](
        message="计划创建成功",
        data=plan,
    )


@router.get("", response_model=ApiResponse[list[PlanRead]])
async def get_plans_api(
    archived: bool = False,
    keyword: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plans = await get_plans_for_user(
        current_user.user_id,
        db,
        archived,
        keyword,
    )
    return ApiResponse[list[PlanRead]](
        message="计划列表获取成功",
        data=plans,
    )


@router.get(
    "/{plan_id}",
    response_model=ApiResponse[PlanRead],
)
async def get_plan_api(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await get_plan_for_user(
        plan_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[PlanRead](
        message="计划获取成功",
        data=plan,
    )


@router.patch(
    "/{plan_id}",
    response_model=ApiResponse[PlanRead],
)
async def update_plan_api(
    plan_id: int,
    plan_update: PlanUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await update_plan_for_user(
        plan_id,
        plan_update,
        current_user.user_id,
        db,
    )
    return ApiResponse[PlanRead](
        message="计划更新成功",
        data=plan,
    )


@router.patch(
    "/{plan_id}/status",
    response_model=ApiResponse[PlanRead],
)
async def update_plan_status_api(
    plan_id: int,
    status_update: PlanStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await update_plan_status_for_user(
        plan_id,
        status_update,
        current_user.user_id,
        db,
    )
    return ApiResponse[PlanRead](
        message="计划状态更新成功",
        data=plan,
    )


@router.delete(
    "/{plan_id}",
    response_model=ApiResponse[PlanRead],
)
async def archive_plan_api(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await archive_plan_for_user(
        plan_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[PlanRead](
        message="计划归档成功",
        data=plan,
    )


@router.post(
    "/{plan_id}/restore",
    response_model=ApiResponse[PlanRead],
)
async def restore_plan_api(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await restore_plan_for_user(
        plan_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[PlanRead](
        message="计划恢复成功",
        data=plan,
    )
