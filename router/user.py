from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services.user import update_my_info
from database.session import get_db
from dependencies.auth import get_current_user
from schemas.response import ApiResponse
from schemas.user import UserInfoUpdate, UserRead
from models.user import User


router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/me", response_model=ApiResponse[UserRead])
async def get_me_api(
    current_user: User = Depends(get_current_user),
):
    return ApiResponse[UserRead](
        message="获取当前用户成功",
        data=UserRead.model_validate(current_user)
    )


@router.patch("/me", response_model=ApiResponse[UserRead])
async def update_my_info_api(
    user_info_update: UserInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await update_my_info(user_info_update, current_user.user_id, db)
    return ApiResponse[UserRead](message="用户资料更新成功", data=data)