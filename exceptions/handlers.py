import logging
from collections.abc import Mapping

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from exceptions.base import AppError
from schemas.response import ApiResponse

logger = logging.getLogger(__name__)


def error_response(
    status_code: int,
    message: str,
    data: object | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    response = ApiResponse[object](
        success=False,
        message=message,
        data=data,
    )

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(response.model_dump()),
        headers=headers,
    )


async def app_error_handler(
    request: Request,
    exc: AppError,
) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        message=exc.message,
        headers=exc.headers,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else "请求失败"
    )

    return error_response(
        status_code=exc.status_code,
        message=message,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(item) for item in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    return error_response(
        status_code=422,
        message="请求参数校验失败",
        data=errors,
    )


async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled exception: %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return error_response(
        status_code=500,
        message="服务器内部错误",
    )