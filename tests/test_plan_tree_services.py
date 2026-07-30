import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from models.enums import CreationSource, PlanStatus, TaskPriority, TaskStatus
from schemas.plan_tree import PlanTaskCreate, PlanTreeCreate
from services import plan_tree as plan_tree_service


def make_db_with_transaction():
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    db = MagicMock()
    db.begin.return_value = transaction
    return db


def make_plan() -> PlanTreeCreate:
    return PlanTreeCreate(
        title="Agent 工程学习",
        goal="完成可部署项目",
        tasks=[
            PlanTaskCreate(
                title="完成后端",
                level=1,
                priority=TaskPriority.HIGH,
                subtasks=[
                    PlanTaskCreate(title="补齐测试", level=2),
                ],
            ),
            PlanTaskCreate(title="部署", level=1),
        ],
    )


def test_create_plan_tree_persists_complete_tree(monkeypatch):
    plan = SimpleNamespace(plan_id=42, title="Agent 工程学习")
    created_tasks = [
        SimpleNamespace(task_id=101),
        SimpleNamespace(task_id=102),
        SimpleNamespace(task_id=103),
    ]
    db = make_db_with_transaction()
    create_plan = AsyncMock(return_value=plan)
    create_task = AsyncMock(side_effect=created_tasks)

    monkeypatch.setattr(
        plan_tree_service,
        "get_plan_by_idempotency_key",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        plan_tree_service,
        "create_plan_by_data",
        create_plan,
    )
    monkeypatch.setattr(
        plan_tree_service,
        "create_task_by_data",
        create_task,
    )

    result = asyncio.run(
        plan_tree_service.create_plan_tree_for_user(
            make_plan(),
            "plan-123",
            user_id=7,
            db=db,
        )
    )

    plan_data = create_plan.await_args.args[0]
    assert plan_data["owner_user_id"] == 7
    assert plan_data["idempotency_key"] == "plan-123"
    assert plan_data["status"] == PlanStatus.ACTIVE
    assert plan_data["creation_source"] == CreationSource.AGENT

    task_calls = create_task.await_args_list
    assert len(task_calls) == 3
    assert task_calls[0].args[0]["parent_task_id"] is None
    assert task_calls[0].args[0]["sort_order"] == 0
    assert task_calls[0].args[0]["level"] == 1
    assert task_calls[0].args[0]["status"] == TaskStatus.PENDING
    assert task_calls[1].args[0]["parent_task_id"] == 101
    assert task_calls[1].args[0]["level"] == 2
    assert task_calls[2].args[0]["sort_order"] == 1
    assert result.plan_id == 42
    assert result.created_task_count == 3


def test_create_plan_tree_reuses_existing_idempotency_key(monkeypatch):
    existing = SimpleNamespace(plan_id=42, title="Agent 工程学习")
    db = make_db_with_transaction()
    create_plan = AsyncMock()

    monkeypatch.setattr(
        plan_tree_service,
        "get_plan_by_idempotency_key",
        AsyncMock(return_value=existing),
    )
    monkeypatch.setattr(
        plan_tree_service,
        "count_tasks_by_plan_id",
        AsyncMock(return_value=3),
    )
    monkeypatch.setattr(
        plan_tree_service,
        "create_plan_by_data",
        create_plan,
    )

    result = asyncio.run(
        plan_tree_service.create_plan_tree_for_user(
            make_plan(),
            "plan-123",
            user_id=7,
            db=db,
        )
    )

    create_plan.assert_not_awaited()
    assert result.plan_id == existing.plan_id
    assert result.created_task_count == 3


def test_create_plan_tree_recovers_from_concurrent_retry(monkeypatch):
    existing = SimpleNamespace(plan_id=42, title="Agent 工程学习")
    db = make_db_with_transaction()

    monkeypatch.setattr(
        plan_tree_service,
        "persist_plan_tree",
        AsyncMock(
            side_effect=IntegrityError(
                "insert plan",
                {},
                Exception("duplicate"),
            )
        ),
    )
    monkeypatch.setattr(
        plan_tree_service,
        "get_plan_by_idempotency_key",
        AsyncMock(return_value=existing),
    )
    monkeypatch.setattr(
        plan_tree_service,
        "count_tasks_by_plan_id",
        AsyncMock(return_value=3),
    )

    result = asyncio.run(
        plan_tree_service.create_plan_tree_for_user(
            make_plan(),
            "plan-123",
            user_id=7,
            db=db,
        )
    )

    assert db.begin.call_count == 2
    assert result.plan_id == existing.plan_id


def test_plan_tree_rejects_invalid_fourth_level():
    with pytest.raises(ValidationError):
        PlanTreeCreate.model_validate(
            {
                "title": "计划",
                "tasks": [
                    {
                        "title": "一级",
                        "level": 1,
                        "subtasks": [
                            {
                                "title": "二级",
                                "level": 2,
                                "subtasks": [
                                    {
                                        "title": "三级",
                                        "level": 3,
                                        "subtasks": [
                                            {
                                                "title": "四级",
                                                "level": 3,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        )
