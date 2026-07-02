from unittest.mock import AsyncMock

from exceptions.task import TaskNotFoundError
from schemas.task import TaskCompleteUpdate, TaskCreate, TaskRead


def test_create_task_success(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    request_body = {
        "title": "学习 pytest",
        "description": "完成 task route tests",
        "tag": "study",
    }
    fake_task = TaskRead(
        task_id=3,
        completed=False,
        **request_body,
    )
    mock_service = AsyncMock(return_value=fake_task)

    monkeypatch.setattr(
        "router.task.create_task_for_user",
        mock_service,
    )

    response = client.post(
        "/api/task/",
        json=request_body,
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "任务创建成功",
        "data": fake_task.model_dump(),
    }

    mock_service.assert_awaited_once_with(
        TaskCreate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_create_task_without_title_returns_422(
    client,
    monkeypatch,
):
    mock_service = AsyncMock()

    monkeypatch.setattr(
        "router.task.create_task_for_user",
        mock_service,
    )

    response = client.post(
        "/api/task/",
        json={"tag": "study"},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["message"] == "请求参数校验失败"
    assert response.json()["data"][0]["field"] == "body.title"

    # 校验失败发生在调用 service 之前
    mock_service.assert_not_awaited()


def test_complete_task_success(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    request_body = {
        "task_id": 4,
        "completed": True,
    }
    fake_task = TaskRead(
        task_id=4,
        title="学习 pytest",
        description=None,
        completed=True,
        tag="study",
    )
    mock_service = AsyncMock(return_value=fake_task)

    monkeypatch.setattr(
        "router.task.complete_task_for_user",
        mock_service,
    )

    response = client.patch(
        "/api/task/complete",
        json=request_body,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "任务完成状态已更新"
    assert response.json()["data"] == fake_task.model_dump()

    mock_service.assert_awaited_once_with(
        TaskCompleteUpdate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_complete_missing_task_returns_404(
    client,
    monkeypatch,
):
    mock_service = AsyncMock(
        side_effect=TaskNotFoundError(),
    )

    monkeypatch.setattr(
        "router.task.complete_task_for_user",
        mock_service,
    )

    response = client.patch(
        "/api/task/complete",
        json={
            "task_id": 999,
            "completed": True,
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "message": "任务不存在",
        "data": None,
    }


def test_delete_task_success(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    mock_service = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "router.task.delete_task_for_user",
        mock_service,
    )

    response = client.delete("/api/task/5")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "任务删除成功",
        "data": None,
    }

    mock_service.assert_awaited_once_with(
        5,
        fake_user.user_id,
        fake_db,
    )


def test_delete_task_with_invalid_id_returns_422(
    client,
    monkeypatch,
):
    mock_service = AsyncMock()

    monkeypatch.setattr(
        "router.task.delete_task_for_user",
        mock_service,
    )

    response = client.delete("/api/task/not-an-integer")

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["message"] == "请求参数校验失败"

    mock_service.assert_not_awaited()


def test_get_tasks_for_user_success(client, fake_user, fake_db, fake_task_factory, monkeypatch):
    fake_tasks = [TaskRead.model_validate(fake_task_factory(task_id=1)), TaskRead.model_validate(fake_task_factory(task_id=2))]
    mock_service = AsyncMock(return_value=fake_tasks)

    monkeypatch.setattr(
        "router.task.get_tasks_for_user",
        mock_service,
    )
    response = client.get("/api/task/")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "任务列表获取成功",
        "data": [task.model_dump() for task in fake_tasks],
    }

    mock_service.assert_awaited_once_with(
        fake_user.user_id,
        fake_db,
        None,
        None,
    )


def test_get_tasks_passes_filters_to_service(client, fake_user, fake_db, monkeypatch):
    mock_service = AsyncMock(return_value=[])

    monkeypatch.setattr(
        "router.task.get_tasks_for_user",
        mock_service,
    )

    response = client.get(
        "/api/task/",
        params={
            "completed": "true",
            "tag": "study",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == []

    # 检查 FastAPI 是否把字符串 "true" 转换为 True
    mock_service.assert_awaited_once_with(
        fake_user.user_id,
        fake_db,
        True,
        "study",
    )
