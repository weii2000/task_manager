from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from database.session import async_engine
from exceptions.base import AppError
from exceptions.handlers import (
    app_error_handler,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
from mcp_server import mcp_http_app, mcp_server
from router import agent, auth, memory, plan, task, user


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with mcp_server.session_manager.run():
            yield
    finally:
        await async_engine.dispose()


app = FastAPI(title="Planwise", lifespan=lifespan)

app.add_exception_handler(
    AppError,
    app_error_handler,  # type: ignore
)

app.add_exception_handler(
    StarletteHTTPException,
    http_exception_handler,  # type: ignore
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,  # type: ignore
)

app.add_exception_handler(
    Exception,
    unexpected_exception_handler,
)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(plan.router)
app.include_router(task.router)
app.include_router(agent.router)
app.include_router(memory.router)
app.mount("/", mcp_http_app)
