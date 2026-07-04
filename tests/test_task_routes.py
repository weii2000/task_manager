from unittest.mock import AsyncMock

from exceptions.task import TaskNotFoundError
from models.enums import TaskStatus
from schemas.task import TaskCreate, TaskStatusUpdate, TaskUpdate


def test_create_task_success(
    client,
    fake_user,
    fake_db,
    fake_task_factory,
    monkeypatch,
):
    request_body = {
        "project_id": 2,
        "title": "学习 pytest",
        "description": "重写 Task Router 测试",
    }
    task = fake_task_factory(task_id=3, project_id=2)
    mock_service = AsyncMock(return_value=task)
    monkeypatch.setattr(
        "router.task.create_task_for_user",
        mock_service,
    )

    response = client.post("/api/tasks", json=request_body)

    assert response.status_code == 201
    assert response.json() == {
        "success": True,
        "message": "任务创建成功",
        "data": task.model_dump(mode="json"),
    }
    mock_service.assert_awaited_once_with(
        TaskCreate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_create_task_rejects_legacy_fields(client, monkeypatch):
    mock_service = AsyncMock()
    monkeypatch.setattr(
        "router.task.create_task_for_user",
        mock_service,
    )

    response = client.post(
        "/api/tasks",
        json={
            "title": "legacy",
            "completed": False,
            "tag": "old",
        },
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
    mock_service.assert_not_awaited()


def test_get_tasks_passes_project_and_archive_filter(
    client,
    fake_user,
    fake_db,
    fake_task_factory,
    monkeypatch,
):
    tasks = [
        fake_task_factory(task_id=1, project_id=3),
        fake_task_factory(task_id=2, project_id=3),
    ]
    mock_service = AsyncMock(return_value=tasks)
    monkeypatch.setattr(
        "router.task.get_project_tasks_for_user",
        mock_service,
    )

    response = client.get(
        "/api/tasks",
        params={"project_id": 3, "archived": "true"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == [
        task.model_dump(mode="json")
        for task in tasks
    ]
    mock_service.assert_awaited_once_with(
        fake_user.user_id,
        fake_db,
        3,
        True,
    )


def test_get_task_success(
    client,
    fake_user,
    fake_db,
    fake_task_factory,
    monkeypatch,
):
    task = fake_task_factory(task_id=4)
    mock_service = AsyncMock(return_value=task)
    monkeypatch.setattr(
        "router.task.get_task_for_user",
        mock_service,
    )

    response = client.get("/api/tasks/4")

    assert response.status_code == 200
    assert response.json()["data"] == task.model_dump(mode="json")
    mock_service.assert_awaited_once_with(
        4,
        fake_user.user_id,
        fake_db,
    )


def test_get_missing_task_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        "router.task.get_task_for_user",
        AsyncMock(side_effect=TaskNotFoundError()),
    )

    response = client.get("/api/tasks/999")

    assert response.status_code == 404
    assert response.json()["message"] == "任务不存在"


def test_update_task_success(
    client,
    fake_user,
    fake_db,
    fake_task_factory,
    monkeypatch,
):
    request_body = {
        "title": "更新后的任务",
        "priority": "high",
    }
    task = fake_task_factory(task_id=5)
    mock_service = AsyncMock(return_value=task)
    monkeypatch.setattr(
        "router.task.update_task_for_user",
        mock_service,
    )

    response = client.patch("/api/tasks/5", json=request_body)

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        5,
        TaskUpdate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_update_task_status_success(
    client,
    fake_user,
    fake_db,
    fake_task_factory,
    monkeypatch,
):
    task = fake_task_factory(task_id=6, status=TaskStatus.DONE)
    mock_service = AsyncMock(return_value=task)
    monkeypatch.setattr(
        "router.task.update_task_status_for_user",
        mock_service,
    )

    response = client.patch(
        "/api/tasks/6/status",
        json={"status": "done"},
    )

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        6,
        TaskStatusUpdate(status=TaskStatus.DONE),
        fake_user.user_id,
        fake_db,
    )


def test_archive_and_restore_task(
    client,
    fake_user,
    fake_db,
    fake_task_factory,
    monkeypatch,
):
    task = fake_task_factory(task_id=7)
    archive_mock = AsyncMock(return_value=task)
    restore_mock = AsyncMock(return_value=task)
    monkeypatch.setattr(
        "router.task.archive_task_for_user",
        archive_mock,
    )
    monkeypatch.setattr(
        "router.task.restore_task_for_user",
        restore_mock,
    )

    archive_response = client.delete("/api/tasks/7")
    restore_response = client.post("/api/tasks/7/restore")

    assert archive_response.status_code == 200
    assert restore_response.status_code == 200
    archive_mock.assert_awaited_once_with(
        7,
        fake_user.user_id,
        fake_db,
    )
    restore_mock.assert_awaited_once_with(
        7,
        fake_user.user_id,
        fake_db,
    )
