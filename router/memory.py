from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agent.long_term_memory import MemoryResolver
from database.session import get_db
from dependencies.agent import get_memory_resolver
from dependencies.auth import get_current_user
from models.enums import MemoryStatus
from models.user import User
from schemas.memory import (
    MemoryConfirmationRequest,
    MemoryConfirmationResponse,
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryRead,
    MemoryUpdateRequest,
)
from schemas.response import ApiResponse
from services.memory import (
    archive_memory_for_user,
    confirm_memory_for_user,
    get_memories_for_user,
    ingest_memories_for_user,
    update_memory_for_user,
)


router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.post(
    "/ingest",
    response_model=ApiResponse[MemoryIngestResponse],
)
async def ingest_memories_api(
    request: MemoryIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    resolver: MemoryResolver = Depends(get_memory_resolver),
) -> ApiResponse[MemoryIngestResponse]:
    result = await ingest_memories_for_user(
        request,
        current_user.user_id,
        db,
        resolver,
    )
    return ApiResponse[MemoryIngestResponse](
        message="长期记忆处理成功",
        data=result,
    )


@router.get("", response_model=ApiResponse[list[MemoryRead]])
async def get_memories_api(
    memory_status: MemoryStatus = Query(
        default=MemoryStatus.ACTIVE,
        alias="status",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[MemoryRead]]:
    memories = await get_memories_for_user(
        current_user.user_id,
        memory_status,
        db,
    )
    return ApiResponse[list[MemoryRead]](
        message="长期记忆列表获取成功",
        data=memories,
    )


@router.post(
    "/{memory_id}/confirmation",
    response_model=ApiResponse[MemoryConfirmationResponse],
)
async def confirm_memory_api(
    memory_id: int,
    request: MemoryConfirmationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    resolver: MemoryResolver = Depends(get_memory_resolver),
) -> ApiResponse[MemoryConfirmationResponse]:
    result = await confirm_memory_for_user(
        memory_id,
        request,
        current_user.user_id,
        db,
        resolver,
    )
    return ApiResponse[MemoryConfirmationResponse](
        message="长期记忆确认处理成功",
        data=result,
    )


@router.patch(
    "/{memory_id}",
    response_model=ApiResponse[MemoryRead],
)
async def update_memory_api(
    memory_id: int,
    request: MemoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MemoryRead]:
    memory = await update_memory_for_user(
        memory_id,
        request,
        current_user.user_id,
        db,
    )
    return ApiResponse[MemoryRead](
        message="长期记忆更新成功",
        data=memory,
    )


@router.delete(
    "/{memory_id}",
    response_model=ApiResponse[MemoryRead],
)
async def archive_memory_api(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MemoryRead]:
    memory = await archive_memory_for_user(
        memory_id,
        current_user.user_id,
        db,
    )
    return ApiResponse[MemoryRead](
        message="长期记忆归档成功",
        data=memory,
    )
