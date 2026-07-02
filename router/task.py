from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from dependencies.auth import get_current_user
from models.user import User
from schemas.response import ApiResponse
from schemas.task import TaskCompleteUpdate, TaskCreate, TaskRead
from services.task import complete_task_for_user, create_task_for_user, delete_task_for_user, get_tasks_for_user


router = APIRouter(prefix="/api/task", tags=["task"])


@router.post("/", response_model=ApiResponse[TaskRead])
async def create_task_for_user_api(
    task_create: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await create_task_for_user(task_create, current_user.user_id, db)
    return ApiResponse[TaskRead](message="任务创建成功", data=data)


@router.patch("/complete", response_model=ApiResponse[TaskRead])
async def complete_task_for_user_api(
    task_complete_update: TaskCompleteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await complete_task_for_user(task_complete_update, current_user.user_id, db)
    return ApiResponse[TaskRead](message="任务完成状态已更新", data=data)


@router.delete("/{task_id}", response_model=ApiResponse)
async def delete_task_for_user_api(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_task_for_user(task_id, current_user.user_id, db)
    return ApiResponse(message="任务删除成功")


@router.get("/", response_model=ApiResponse[list[TaskRead]])
async def get_tasks_for_user_api(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    completed: bool | None = None,
    tag: str | None = None
):
    data = await get_tasks_for_user(current_user.user_id, db, completed, tag)
    return ApiResponse[list[TaskRead]](message="任务列表获取成功", data=data)
    
