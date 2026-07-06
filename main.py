from fastapi import FastAPI
from contextlib import asynccontextmanager

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


from database.session import async_engine
from router import auth, project, task, user, agent
from exceptions.base import AppError
from exceptions.handlers import app_error_handler, http_exception_handler, validation_exception_handler, unexpected_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await async_engine.dispose()


app = FastAPI(lifespan=lifespan)

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
app.include_router(project.router)
app.include_router(task.router)
app.include_router(agent.router)
