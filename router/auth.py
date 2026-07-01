from fastapi import APIRouter, Depends, Cookie, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.cookies import delete_refresh_cookie, set_refresh_cookie
from schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from services.auth import login, logout, refresh, register
from database.session import get_db
from schemas.response import ApiResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse[AuthResponse])
async def register_api(
    register_request: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    data, refresh_token = await register(register_request, db)
    set_refresh_cookie(response, refresh_token)
    return ApiResponse[AuthResponse](message="注册成功", data=data)


@router.post("/login", response_model=ApiResponse[AuthResponse])
async def login_api(
    login_request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    data, refresh_token = await login(login_request, db)
    set_refresh_cookie(response, refresh_token)
    return ApiResponse[AuthResponse](message="登陆成功", data=data) 


@router.post("/logout", response_model=ApiResponse[AuthResponse])
async def logout_api(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="refreshToken"),
    db: AsyncSession = Depends(get_db),
):
    await logout(refresh_token, db)
    delete_refresh_cookie(response)

    return ApiResponse(message="退出成功")


@router.post("/refresh", response_model=ApiResponse[AuthResponse])
async def refresh_api(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="refreshToken"),
    db: AsyncSession = Depends(get_db),
):
    data, new_refresh_token = await refresh(refresh_token, db)
    set_refresh_cookie(response, new_refresh_token)
    return ApiResponse[AuthResponse](message="刷新成功", data=data)