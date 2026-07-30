from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from database.session import get_db
from dependencies.auth import get_current_user
from main import app
from models.enums import (
    CreationSource,
    PlanStatus,
    PlanSystemType,
    TaskPriority,
    TaskStatus,
)
from schemas.plan import PlanRead
from schemas.task import TaskRead


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


def make_fake_plan(
    plan_id: int = 1,
    owner_user_id: int = 1,
    status: PlanStatus = PlanStatus.ACTIVE,
    system_type: PlanSystemType | None = None,
    archived_time: datetime | None = None,
) -> PlanRead:
    return PlanRead(
        plan_id=plan_id,
        owner_user_id=owner_user_id,
        title=f"Plan {plan_id}",
        description=None,
        goal=None,
        status=status,
        creation_source=CreationSource.MANUAL,
        system_type=system_type,
        start_time=None,
        due_time=None,
        completed_time=None,
        archived_time=archived_time,
        created_time=datetime(2026, 7, 4, 10),
        updated_time=datetime(2026, 7, 4, 10),
    )


@pytest.fixture
def fake_plan_factory():
    return make_fake_plan


def make_fake_task(
    task_id: int = 1,
    plan_id: int = 1,
    parent_task_id: int | None = None,
    level: int = 1,
    status: TaskStatus = TaskStatus.PENDING,
    archived_time: datetime | None = None,
) -> TaskRead:
    return TaskRead(
        task_id=task_id,
        plan_id=plan_id,
        parent_task_id=parent_task_id,
        level=level,
        title=f"Task {task_id}",
        description=f"Description {task_id}",
        acceptance_criteria=None,
        sort_order=0,
        status=status,
        priority=TaskPriority.LOW,
        creation_source=CreationSource.MANUAL,
        start_time=None,
        due_time=None,
        completed_time=None,
        archived_time=archived_time,
        created_time=datetime(2026, 7, 4, 10),
        updated_time=datetime(2026, 7, 4, 10),
    )


@pytest.fixture
def fake_task_factory():
    return make_fake_task


@pytest.fixture(autouse=True)
def app_dependency_overrides(fake_user, fake_db):
    async def override_get_current_user():
        return fake_user

    async def override_get_db():
        return fake_db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def app_client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(app_client):
    app_client.cookies.clear()
    yield app_client
    app_client.cookies.clear()
