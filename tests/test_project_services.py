import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.project import IncompleteProjectTasksError
from models.enums import ProjectStatus
from schemas.project import ProjectStatusUpdate
from services import project as project_service


def make_db_with_transaction():
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    db = MagicMock()
    db.begin.return_value = transaction
    return db


def test_project_cannot_complete_with_incomplete_tasks(
    fake_project_factory,
    monkeypatch,
):
    project = fake_project_factory(
        project_id=2,
        status=ProjectStatus.ACTIVE,
    )
    db = make_db_with_transaction()
    update_mock = AsyncMock()

    monkeypatch.setattr(
        project_service,
        "get_project_by_id_and_owner_user_id",
        AsyncMock(return_value=project),
    )
    monkeypatch.setattr(
        project_service,
        "has_incomplete_project_tasks",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        project_service,
        "update_project_by_data",
        update_mock,
    )

    with pytest.raises(IncompleteProjectTasksError):
        asyncio.run(
            project_service.update_project_status_for_user(
                project.project_id,
                ProjectStatusUpdate(
                    status=ProjectStatus.COMPLETED,
                ),
                project.owner_user_id,
                db,
            )
        )

    update_mock.assert_not_awaited()
