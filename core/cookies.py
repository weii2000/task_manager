from fastapi import Response

from core.config import settings

REFRESH_COOKIE_NAME = "refreshToken"


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=False,  # 本地 HTTP 开发使用 False，生产 HTTPS 使用 True
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",
    )


def delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/auth",
    )