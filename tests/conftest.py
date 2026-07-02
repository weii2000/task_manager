import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

from main import app
from database.session import get_db
from dependencies.auth import get_current_user


@pytest.fixture
def fake_user():
    return SimpleNamespace(
        user_id=1,
        username="alice",
        email="alice@example.com",
        bio="hello",
    )


@pytest.fixture
def fake_db():
    return object()


def make_fake_task(task_id: int = 1, completed: bool = False, user_id: int = 1, tag: str = "random"):
    return SimpleNamespace(
        task_id=task_id,
        title=f'fake task {task_id}',
        description=f'This is fake task {task_id}',
        tag=tag,
        completed=completed,
        user_id=user_id,
    )


@pytest.fixture
def fake_task_factory():
    return make_fake_task


@pytest.fixture
def client(fake_user, fake_db):

    async def override_get_current_user():
        return fake_user
    async def override_get_db():
        return fake_db

    # 测试时用假函数替换真实登录验证
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # 测试结束后清理
    app.dependency_overrides.clear()