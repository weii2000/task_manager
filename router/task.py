from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from dependencies.auth import get_current_user
from models.user import User
from schemas.response import ApiResponse
from schemas.task import (
    TaskCreate,
    TaskRead,
    TaskStatusUpdate,
    TaskUpdate,
)
from services.task import (
    archive_task_for_user,
    create_task_for_user,
    get_plan_tasks_for_user,
    get_task_for_user,
    restore_task_for_user,
    update_task_for_user,
    update_task_status_for_user,
)

router = APIRouter(
    prefix="/api/tasks",
    tags=["tasks"],
)


@router.post(
    "",
    response_model=ApiResponse[TaskRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_task_api(
    task_create: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await create_task_for_user(
        task_create,
        current_user.user_id,
        db,
    )
    return ApiResponse[TaskRead](
        message="任务创建成功",
        data=task,
    )


@router.get("", response_model=ApiResponse[list[TaskRead]])
async def get_tasks_api(
    plan_id: int | None = None,
    archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await get_plan_tasks_for_user(
        current_user.user_id,
        db,
        plan_id,
        archived,
    )
    return ApiResponse[list[TaskRead]](
        message="任务列表获取成功",
        data=tasks,
    )


@router.get("/{task_id}", response_model=ApiResponse[TaskRead])
async def get_task_api(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await get_task_for_user(
        task_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[TaskRead](
        message="任务获取成功",
        data=task,
    )


@router.patch("/{task_id}", response_model=ApiResponse[TaskRead])
async def update_task_api(
    task_id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await update_task_for_user(
        task_id,
        task_update,
        current_user.user_id,
        db,
    )
    return ApiResponse[TaskRead](
        message="任务更新成功",
        data=task,
    )


@router.patch(
    "/{task_id}/status",
    response_model=ApiResponse[TaskRead],
)
async def update_task_status_api(
    task_id: int,
    status_update: TaskStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await update_task_status_for_user(
        task_id,
        status_update,
        current_user.user_id,
        db,
    )
    return ApiResponse[TaskRead](
        message="任务状态更新成功",
        data=task,
    )


@router.delete(
    "/{task_id}",
    response_model=ApiResponse[TaskRead],
)
async def archive_task_api(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await archive_task_for_user(
        task_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[TaskRead](
        message="任务归档成功",
        data=task,
    )


@router.post(
    "/{task_id}/restore",
    response_model=ApiResponse[TaskRead],
)
async def restore_task_api(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await restore_task_for_user(
        task_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[TaskRead](
        message="任务恢复成功",
        data=task,
    )
