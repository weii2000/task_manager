from unittest.mock import AsyncMock

from models.enums import ProjectStatus
from schemas.project import (
    ProjectCreate,
    ProjectStatusUpdate,
    ProjectUpdate,
)


def test_create_project_success(
    client,
    fake_user,
    fake_db,
    fake_project_factory,
    monkeypatch,
):
    request_body = {
        "title": "毕业设计",
        "goal": "完成 Agent 任务管理系统",
    }
    project = fake_project_factory(project_id=2)
    mock_service = AsyncMock(return_value=project)
    monkeypatch.setattr(
        "router.project.create_project_for_user",
        mock_service,
    )

    response = client.post("/api/projects", json=request_body)

    assert response.status_code == 201
    assert response.json()["data"] == project.model_dump(mode="json")
    mock_service.assert_awaited_once_with(
        ProjectCreate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_create_project_rejects_system_fields(client, monkeypatch):
    mock_service = AsyncMock()
    monkeypatch.setattr(
        "router.project.create_project_for_user",
        mock_service,
    )

    response = client.post(
        "/api/projects",
        json={
            "title": "非法项目",
            "system_type": "inbox",
        },
    )

    assert response.status_code == 422
    mock_service.assert_not_awaited()


def test_get_projects_passes_archive_filter(
    client,
    fake_user,
    fake_db,
    fake_project_factory,
    monkeypatch,
):
    projects = [fake_project_factory(project_id=2)]
    mock_service = AsyncMock(return_value=projects)
    monkeypatch.setattr(
        "router.project.get_projects_for_user",
        mock_service,
    )

    response = client.get(
        "/api/projects",
        params={"archived": "true"},
    )

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        fake_user.user_id,
        fake_db,
        True,
    )


def test_get_project_success(
    client,
    fake_user,
    fake_db,
    fake_project_factory,
    monkeypatch,
):
    project = fake_project_factory(project_id=3)
    mock_service = AsyncMock(return_value=project)
    monkeypatch.setattr(
        "router.project.get_project_for_user",
        mock_service,
    )

    response = client.get("/api/projects/3")

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        3,
        fake_user.user_id,
        fake_db,
    )


def test_update_project_success(
    client,
    fake_user,
    fake_db,
    fake_project_factory,
    monkeypatch,
):
    request_body = {"title": "新标题"}
    project = fake_project_factory(project_id=4)
    mock_service = AsyncMock(return_value=project)
    monkeypatch.setattr(
        "router.project.update_project_for_user",
        mock_service,
    )

    response = client.patch("/api/projects/4", json=request_body)

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        4,
        ProjectUpdate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_update_project_status_success(
    client,
    fake_user,
    fake_db,
    fake_project_factory,
    monkeypatch,
):
    project = fake_project_factory(
        project_id=5,
        status=ProjectStatus.ACTIVE,
    )
    mock_service = AsyncMock(return_value=project)
    monkeypatch.setattr(
        "router.project.update_project_status_for_user",
        mock_service,
    )

    response = client.patch(
        "/api/projects/5/status",
        json={"status": "active"},
    )

    assert response.status_code == 200
    mock_service.assert_awaited_once_with(
        5,
        ProjectStatusUpdate(status=ProjectStatus.ACTIVE),
        fake_user.user_id,
        fake_db,
    )


def test_archive_and_restore_project(
    client,
    fake_user,
    fake_db,
    fake_project_factory,
    monkeypatch,
):
    project = fake_project_factory(project_id=6)
    archive_mock = AsyncMock(return_value=project)
    restore_mock = AsyncMock(return_value=project)
    monkeypatch.setattr(
        "router.project.archive_project_for_user",
        archive_mock,
    )
    monkeypatch.setattr(
        "router.project.restore_project_for_user",
        restore_mock,
    )

    archive_response = client.delete("/api/projects/6")
    restore_response = client.post("/api/projects/6/restore")

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
