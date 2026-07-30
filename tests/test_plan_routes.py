from unittest.mock import AsyncMock

from models.enums import PlanStatus
from schemas.plan import (
    PlanCreate,
    PlanStatusUpdate,
    PlanUpdate,
)


def test_create_plan_success(
    client,
    fake_user,
    fake_db,
    fake_plan_factory,
    monkeypatch,
):
    request_body = {
        "title": "毕业设计",
        "goal": "完成 Agent 任务管理系统",
    }
    plan = fake_plan_factory(plan_id=2)
    mock_service = AsyncMock(return_value=plan)
    monkeypatch.setattr(
        "router.plan.create_plan_for_user",
        mock_service,
    )

    response = client.post("/api/plans", json=request_body)

    assert response.status_code == 201
    assert response.json()["data"] == plan.model_dump(mode="json")
    mock_service.assert_awaited_once_with(
        PlanCreate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_create_plan_rejects_system_fields(client, monkeypatch):
    mock_service = AsyncMock()
    monkeypatch.setattr(
        "router.plan.create_plan_for_user",
        mock_service,
    )

    response = client.post(
        "/api/plans",
        json={
            "title": "非法计划",
            "system_type": "inbox",
        },
    )

    assert response.status_code == 422
    mock_service.assert_not_awaited()


def test_get_plans_passes_archive_filter(
    client,
    fake_user,
    fake_db,
    fake_plan_factory,
    monkeypatch,
):
    plans = [fake_plan_factory(plan_id=2)]
    mock_service = AsyncMock(return_value=plans)
    monkeypatch.setattr(
        "router.plan.get_plans_for_user",
        mock_service,
    )

    response = client.get(
        "/api/plans",
        params={"archived": "true"},
    )

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        fake_user.user_id,
        fake_db,
        True,
        None,
    )


def test_get_plan_success(
    client,
    fake_user,
    fake_db,
    fake_plan_factory,
    monkeypatch,
):
    plan = fake_plan_factory(plan_id=3)
    mock_service = AsyncMock(return_value=plan)
    monkeypatch.setattr(
        "router.plan.get_plan_for_user",
        mock_service,
    )

    response = client.get("/api/plans/3")

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        3,
        fake_user.user_id,
        fake_db,
    )


def test_update_plan_success(
    client,
    fake_user,
    fake_db,
    fake_plan_factory,
    monkeypatch,
):
    request_body = {"title": "新标题"}
    plan = fake_plan_factory(plan_id=4)
    mock_service = AsyncMock(return_value=plan)
    monkeypatch.setattr(
        "router.plan.update_plan_for_user",
        mock_service,
    )

    response = client.patch("/api/plans/4", json=request_body)

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        4,
        PlanUpdate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_update_plan_status_success(
    client,
    fake_user,
    fake_db,
    fake_plan_factory,
    monkeypatch,
):
    plan = fake_plan_factory(
        plan_id=5,
        status=PlanStatus.ACTIVE,
    )
    mock_service = AsyncMock(return_value=plan)
    monkeypatch.setattr(
        "router.plan.update_plan_status_for_user",
        mock_service,
    )

    response = client.patch(
        "/api/plans/5/status",
        json={"status": "active"},
    )

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        5,
        PlanStatusUpdate(status=PlanStatus.ACTIVE),
        fake_user.user_id,
        fake_db,
    )


def test_archive_and_restore_plan(
    client,
    fake_user,
    fake_db,
    fake_plan_factory,
    monkeypatch,
):
    plan = fake_plan_factory(plan_id=6)
    archive_mock = AsyncMock(return_value=plan)
    restore_mock = AsyncMock(return_value=plan)
    monkeypatch.setattr(
        "router.plan.archive_plan_for_user",
        archive_mock,
    )
    monkeypatch.setattr(
        "router.plan.restore_plan_for_user",
        restore_mock,
    )

    archive_response = client.delete("/api/plans/6")
    restore_response = client.post("/api/plans/6/restore")

    assert archive_response.status_code == 200
    assert restore_response.status_code == 200
    archive_mock.assert_awaited_once_with(
        6,
        fake_user.user_id,
        fake_db,
    )
    restore_mock.assert_awaited_once_with(
        6,
        fake_user.user_id,
        fake_db,
    )
