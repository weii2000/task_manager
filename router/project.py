from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from dependencies.auth import get_current_user
from models.user import User
from schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectStatusUpdate,
    ProjectUpdate,
)
from schemas.response import ApiResponse
from services.project import (
    archive_project_for_user,
    create_project_for_user,
    get_project_for_user,
    get_projects_for_user,
    restore_project_for_user,
    update_project_status_for_user,
    update_project_for_user,
)


router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
)


@router.post(
    "",
    response_model=ApiResponse[ProjectRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_project_api(
    project_create: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await create_project_for_user(
        project_create,
        current_user.user_id,
        db,
    )
    return ApiResponse[ProjectRead](
        message="项目创建成功",
        data=project,
    )


@router.get("", response_model=ApiResponse[list[ProjectRead]])
async def get_projects_api(
    archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects = await get_projects_for_user(
        current_user.user_id,
        db,
        archived,
    )
    return ApiResponse[list[ProjectRead]](
        message="项目列表获取成功",
        data=projects,
    )


@router.get(
    "/{project_id}",
    response_model=ApiResponse[ProjectRead],
)
async def get_project_api(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_for_user(
        project_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[ProjectRead](
        message="项目获取成功",
        data=project,
    )


@router.patch(
    "/{project_id}",
    response_model=ApiResponse[ProjectRead],
)
async def update_project_api(
    project_id: int,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await update_project_for_user(
        project_id,
        project_update,
        current_user.user_id,
        db,
    )
    return ApiResponse[ProjectRead](
        message="项目更新成功",
        data=project,
    )


@router.patch(
    "/{project_id}/status",
    response_model=ApiResponse[ProjectRead],
)
async def update_project_status_api(
    project_id: int,
    status_update: ProjectStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await update_project_status_for_user(
        project_id,
        status_update,
        current_user.user_id,
        db,
    )
    return ApiResponse[ProjectRead](
        message="项目状态更新成功",
        data=project,
    )


@router.delete(
    "/{project_id}",
    response_model=ApiResponse[ProjectRead],
)
async def archive_project_api(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await archive_project_for_user(
        project_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[ProjectRead](
        message="项目归档成功",
        data=project,
    )


@router.post(
    "/{project_id}/restore",
    response_model=ApiResponse[ProjectRead],
)
async def restore_project_api(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await restore_project_for_user(
        project_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[ProjectRead](
        message="项目恢复成功",
        data=project,
    )
