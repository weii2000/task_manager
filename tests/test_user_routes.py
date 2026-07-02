from unittest.mock import AsyncMock

from exceptions.user import EmptyUserUpdateError
from schemas.user import UserInfoUpdate, UserRead


def test_get_me_success(client, fake_user):
    response = client.get("/api/user/me")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "获取当前用户成功",
        "data": {
            "username": fake_user.username,
            "email": fake_user.email,
            "bio": fake_user.bio,
        },
    }


def test_update_me_success(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    request_body = {
        "email": "new@example.com",
        "bio": "updated bio",
    }
    updated_user = UserRead(
        username=fake_user.username,
        **request_body,
    )
    mock_service = AsyncMock(return_value=updated_user)

    monkeypatch.setattr(
        "router.user.update_my_info",
        mock_service,
    )

    response = client.patch(
        "/api/user/me",
        json=request_body,
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "用户资料更新成功",
        "data": updated_user.model_dump(),
    }

    mock_service.assert_awaited_once_with(
        UserInfoUpdate(**request_body),
        fake_user.user_id,
        fake_db,
    )


def test_update_me_with_empty_body_returns_400(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    mock_service = AsyncMock(
        side_effect=EmptyUserUpdateError(),
    )

    monkeypatch.setattr(
        "router.user.update_my_info",
        mock_service,
    )

    response = client.patch(
        "/api/user/me",
        json={},
    )

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "message": "没有需要更新的用户资料",
        "data": None,
    }

    mock_service.assert_awaited_once_with(
        UserInfoUpdate(),
        fake_user.user_id,
        fake_db,
    )
