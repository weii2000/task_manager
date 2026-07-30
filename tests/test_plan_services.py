import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.plan import IncompletePlanTasksError
from models.enums import PlanStatus
from schemas.plan import PlanStatusUpdate
from services import plan as plan_service


def make_db_with_transaction():
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    db = MagicMock()
    db.begin.return_value = transaction
    return db


def test_plan_cannot_complete_with_incomplete_tasks(
    fake_plan_factory,
    monkeypatch,
):
    plan = fake_plan_factory(
        plan_id=2,
        status=PlanStatus.ACTIVE,
    )
    db = make_db_with_transaction()
    update_mock = AsyncMock()

    monkeypatch.setattr(
        plan_service,
        "get_plan_by_id_and_owner_user_id",
        AsyncMock(return_value=plan),
    )
    monkeypatch.setattr(
        plan_service,
        "has_incomplete_plan_tasks",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        plan_service,
        "update_plan_by_data",
        update_mock,
    )

    with pytest.raises(IncompletePlanTasksError):
        asyncio.run(
            plan_service.update_plan_status_for_user(
                plan.plan_id,
                PlanStatusUpdate(
                    status=PlanStatus.COMPLETED,
                ),
                plan.owner_user_id,
                db,
            )
        )

    update_mock.assert_not_awaited()
