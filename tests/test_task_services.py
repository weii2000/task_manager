import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.task import (
    IncompleteChildTasksError,
    ParentTaskPlanMismatchError,
    TaskLevelLimitExceededError,
)
from models.enums import (
    CreationSource,
    PlanStatus,
    PlanSystemType,
    TaskStatus,
)
from schemas.task import TaskCreate, TaskStatusUpdate
from services import task as task_service


def make_db_with_transaction():
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    db = MagicMock()
    db.begin.return_value = transaction
    return db


def test_create_task_without_plan_uses_inbox(
    fake_plan_factory,
    fake_task_factory,
    monkeypatch,
):
    inbox = fake_plan_factory(
        plan_id=10,
        status=PlanStatus.ACTIVE,
        system_type=PlanSystemType.INBOX,
    )
    task = fake_task_factory(task_id=3, plan_id=inbox.plan_id)
    db = make_db_with_transaction()
    create_mock = AsyncMock(return_value=task)

    monkeypatch.setattr(
        task_service,
        "get_inbox_plan_by_owner_user_id",
        AsyncMock(return_value=inbox),
    )
    monkeypatch.setattr(
        task_service,
        "create_task_by_data",
        create_mock,
    )

    result = asyncio.run(
        task_service.create_task_for_user(
            TaskCreate(title="Inbox task"),
            inbox.owner_user_id,
            db,
        )
    )

    created_data = create_mock.await_args.args[0]
    assert created_data["plan_id"] == inbox.plan_id
    assert created_data["creation_source"] == CreationSource.MANUAL
    assert result.task_id == task.task_id


def test_create_task_rejects_parent_plan_mismatch(
    fake_task_factory,
    monkeypatch,
):
    parent = fake_task_factory(task_id=8, plan_id=2)
    db = make_db_with_transaction()

    monkeypatch.setattr(
        task_service,
        "get_task_by_id_and_owner_user_id",
        AsyncMock(return_value=parent),
    )

    with pytest.raises(ParentTaskPlanMismatchError):
        asyncio.run(
            task_service.create_task_for_user(
                TaskCreate(
                    title="Child",
                    plan_id=3,
                    parent_task_id=parent.task_id,
                ),
                1,
                db,
            )
        )


def test_create_task_rejects_fourth_level(
    fake_task_factory,
    monkeypatch,
):
    parent = fake_task_factory(task_id=8, plan_id=2, level=3)
    monkeypatch.setattr(
        task_service,
        "get_task_by_id_and_owner_user_id",
        AsyncMock(return_value=parent),
    )

    with pytest.raises(TaskLevelLimitExceededError):
        asyncio.run(
            task_service.create_task_for_user(
                TaskCreate(title="第四级", parent_task_id=parent.task_id),
                1,
                make_db_with_transaction(),
            )
        )


def test_task_cannot_complete_with_incomplete_children(
    fake_plan_factory,
    fake_task_factory,
    monkeypatch,
):
    plan = fake_plan_factory(
        plan_id=4,
        status=PlanStatus.ACTIVE,
    )
    task = fake_task_factory(
        task_id=9,
        plan_id=plan.plan_id,
        status=TaskStatus.IN_PROGRESS,
    )
    db = make_db_with_transaction()
    update_mock = AsyncMock()

    monkeypatch.setattr(
        task_service,
        "get_task_by_id_and_owner_user_id",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        task_service,
        "get_plan_by_id_and_owner_user_id",
        AsyncMock(return_value=plan),
    )
    monkeypatch.setattr(
        task_service,
        "has_incomplete_child_tasks",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        task_service,
        "update_task_by_data",
        update_mock,
    )

    with pytest.raises(IncompleteChildTasksError):
        asyncio.run(
            task_service.update_task_status_for_user(
                task.task_id,
                TaskStatusUpdate(status=TaskStatus.COMPLETED),
                plan.owner_user_id,
                db,
            )
        )

    update_mock.assert_not_awaited()
