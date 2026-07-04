import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from models.enums import CreationSource, ProjectStatus, ProjectSystemType
from schemas.auth import RegisterRequest
from services import auth as auth_service


def test_register_creates_inbox_project(monkeypatch):
    user = SimpleNamespace(
        user_id=1,
        username="alice",
        email=None,
        bio=None,
    )
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)

    db = MagicMock()
    db.begin.return_value = transaction
    db.refresh = AsyncMock()

    monkeypatch.setattr(
        auth_service,
        "get_user_by_username",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        auth_service,
        "get_hashed_password",
        MagicMock(return_value="hashed-password"),
    )
    monkeypatch.setattr(
        auth_service,
        "create_user",
        AsyncMock(return_value=user),
    )
    create_project_mock = AsyncMock()
    monkeypatch.setattr(
        auth_service,
        "create_project_by_data",
        create_project_mock,
    )
    monkeypatch.setattr(
        auth_service,
        "create_access_token",
        MagicMock(return_value="access-token"),
    )
    monkeypatch.setattr(
        auth_service,
        "create_refresh_token",
        MagicMock(
            return_value=(
                "refresh-token",
                datetime(2026, 7, 5),
            ),
        ),
    )
    monkeypatch.setattr(
        auth_service,
        "hash_token",
        MagicMock(return_value="refresh-token-hash"),
    )
    create_refresh_token_record_mock = AsyncMock()
    monkeypatch.setattr(
        auth_service,
        "create_refresh_token_record",
        create_refresh_token_record_mock,
    )

    auth_response, refresh_token = asyncio.run(
        auth_service.register(
            RegisterRequest(
                username="alice",
                password="password123",
            ),
            db,
        )
    )

    create_project_mock.assert_awaited_once_with(
        {
            "owner_user_id": user.user_id,
            "title": "Inbox",
            "status": ProjectStatus.ACTIVE,
            "creation_source": CreationSource.SYSTEM,
            "system_type": ProjectSystemType.INBOX,
        },
        db,
    )
    create_refresh_token_record_mock.assert_awaited_once_with(
        "refresh-token-hash",
        datetime(2026, 7, 5),
        user.user_id,
        db,
    )
    transaction.__aenter__.assert_awaited_once()
    transaction.__aexit__.assert_awaited_once()
    assert auth_response.user.username == "alice"
    assert refresh_token == "refresh-token"
