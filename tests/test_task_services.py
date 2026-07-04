import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.task import (
    IncompleteChildTasksError,
    ParentTaskProjectMismatchError,
)
from models.enums import (
    CreationSource,
    ProjectStatus,
    ProjectSystemType,
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


def test_create_task_without_project_uses_inbox(
    fake_project_factory,
    fake_task_factory,
    monkeypatch,
):
    inbox = fake_project_factory(
        project_id=10,
        status=ProjectStatus.ACTIVE,
        system_type=ProjectSystemType.INBOX,
    )
    task = fake_task_factory(task_id=3, project_id=inbox.project_id)
    db = make_db_with_transaction()
    create_mock = AsyncMock(return_value=task)

    monkeypatch.setattr(
        task_service,
        "get_inbox_project_by_owner_user_id",
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
    assert created_data["project_id"] == inbox.project_id
    assert created_data["creation_source"] == CreationSource.MANUAL
    assert result.task_id == task.task_id


def test_create_task_rejects_parent_project_mismatch(
    fake_task_factory,
    monkeypatch,
):
    parent = fake_task_factory(task_id=8, project_id=2)
    db = make_db_with_transaction()

    monkeypatch.setattr(
        task_service,
        "get_task_by_id_and_owner_user_id",
        AsyncMock(return_value=parent),
    )

    with pytest.raises(ParentTaskProjectMismatchError):
        asyncio.run(
            task_service.create_task_for_user(
                TaskCreate(
                    title="Child",
                    project_id=3,
                    parent_task_id=parent.task_id,
                ),
                1,
                db,
            )
        )


def test_task_cannot_complete_with_incomplete_children(
    fake_project_factory,
    fake_task_factory,
    monkeypatch,
):
    project = fake_project_factory(
        project_id=4,
        status=ProjectStatus.ACTIVE,
    )
    task = fake_task_factory(
        task_id=9,
        project_id=project.project_id,
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
        "get_project_by_id_and_owner_user_id",
        AsyncMock(return_value=project),
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
                TaskStatusUpdate(status=TaskStatus.DONE),
                project.owner_user_id,
                db,
            )
        )

    update_mock.assert_not_awaited()
