from unittest.mock import AsyncMock

from exceptions.auth import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
)
from schemas.user import UserRead


def make_auth_response(fake_user, access_token="access-token"):
    return AuthResponse(access_token=access_token, user=UserRead.model_validate(fake_user)) # type:ignore


def test_register_success(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    request_body = {
        "username": "new-user",
        "password": "password123",
    }
    auth_data = make_auth_response(fake_user)
    mock_service = AsyncMock(
        return_value=(auth_data, "refresh-token"),
    )

    monkeypatch.setattr(
        "router.auth.register",
        mock_service,
    )

    response = client.post(
        "/api/auth/register",
        json=request_body,
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "注册成功",
        "data": auth_data.model_dump(by_alias=True),
    }
    assert response.cookies.get("refreshToken") == "refresh-token"

    mock_service.assert_awaited_once_with(
        RegisterRequest(**request_body),
        fake_db,
    )


def test_register_without_password_returns_422(
    client,
    monkeypatch,
):
    mock_service = AsyncMock()

    monkeypatch.setattr(
        "router.auth.register",
        mock_service,
    )

    response = client.post(
        "/api/auth/register",
        json={"username": "new-user"},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["message"] == "请求参数校验失败"
    assert response.json()["data"][0]["field"] == "body.password"

    mock_service.assert_not_awaited()


def test_login_success(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    request_body = {
        "username": "alice",
        "password": "password123",
    }
    auth_data = make_auth_response(fake_user)
    mock_service = AsyncMock(
        return_value=(auth_data, "refresh-token"),
    )

    monkeypatch.setattr(
        "router.auth.login",
        mock_service,
    )

    response = client.post(
        "/api/auth/login",
        json=request_body,
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "登陆成功",
        "data": auth_data.model_dump(by_alias=True),
    }
    assert response.cookies.get("refreshToken") == "refresh-token"

    mock_service.assert_awaited_once_with(
        LoginRequest(**request_body),
        fake_db,
    )


def test_login_with_invalid_credentials_returns_401(
    client,
    fake_db,
    monkeypatch,
):
    request_body = {
        "username": "alice",
        "password": "wrong-password",
    }
    mock_service = AsyncMock(
        side_effect=InvalidCredentialsError(),
    )

    monkeypatch.setattr(
        "router.auth.login",
        mock_service,
    )

    response = client.post(
        "/api/auth/login",
        json=request_body,
    )

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "message": "用户名或密码错误",
        "data": None,
    }
    assert response.headers["www-authenticate"] == "Bearer"

    mock_service.assert_awaited_once_with(
        LoginRequest(**request_body),
        fake_db,
    )


def test_logout_success(
    client,
    fake_db,
    monkeypatch,
):
    mock_service = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "router.auth.logout",
        mock_service,
    )

    client.cookies.set(
        "refreshToken",
        "old-refresh-token",
        path="/api/auth",
    )

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "退出成功",
        "data": None,
    }
    assert "Max-Age=0" in response.headers["set-cookie"]

    mock_service.assert_awaited_once_with(
        "old-refresh-token",
        fake_db,
    )


def test_logout_without_cookie_returns_401(
    client,
    fake_db,
    monkeypatch,
):
    mock_service = AsyncMock(
        side_effect=InvalidRefreshTokenError(),
    )

    monkeypatch.setattr(
        "router.auth.logout",
        mock_service,
    )

    response = client.post("/api/auth/logout")

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "message": "刷新凭证无效或已过期",
        "data": None,
    }

    mock_service.assert_awaited_once_with(
        None,
        fake_db,
    )


def test_refresh_success(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    auth_data = make_auth_response(
        fake_user,
        access_token="new-access-token",
    )
    mock_service = AsyncMock(
        return_value=(auth_data, "new-refresh-token"),
    )

    monkeypatch.setattr(
        "router.auth.refresh",
        mock_service,
    )

    client.cookies.set(
        "refreshToken",
        "old-refresh-token",
        path="/api/auth",
    )

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "刷新成功",
        "data": auth_data.model_dump(by_alias=True),
    }
    assert response.cookies.get("refreshToken") == "new-refresh-token"

    mock_service.assert_awaited_once_with(
        "old-refresh-token",
        fake_db,
    )
