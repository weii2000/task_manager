from datetime import datetime, timezone
from unittest.mock import AsyncMock

from dependencies.agent import get_memory_resolver
from main import app
from models.enums import MemoryCategory, MemorySource, MemoryStatus
from schemas.memory import (
    MemoryConfirmationRequest,
    MemoryConfirmationResponse,
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryRead,
)


def make_memory_read() -> MemoryRead:
    now = datetime(2026, 7, 13, 10, tzinfo=timezone.utc)
    return MemoryRead(
        memory_id=1,
        category=MemoryCategory.PREFERENCE,
        content="用户偏好一小时以内的任务",
        status=MemoryStatus.ACTIVE,
        source=MemorySource.MANUAL,
        version=1,
        source_agent_session_id=None,
        source_message_index=None,
        created_time=now,
        updated_time=now,
    )


def test_ingest_memory_route(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    resolver = object()

    async def override_memory_resolver():
        return resolver

    app.dependency_overrides[
        get_memory_resolver
    ] = override_memory_resolver
    result = MemoryIngestResponse(created=[make_memory_read()])
    ingest = AsyncMock(return_value=result)
    monkeypatch.setattr(
        "router.memory.ingest_memories_for_user",
        ingest,
    )

    response = client.post(
        "/api/memories/ingest",
        json={"text": "请记住我偏好一小时以内的任务"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["created"][0]["memory_id"] == 1
    ingest.assert_awaited_once_with(
        MemoryIngestRequest(
            text="请记住我偏好一小时以内的任务"
        ),
        fake_user.user_id,
        fake_db,
        resolver,
    )


def test_ingest_memory_rejects_blank_text(client):
    async def override_memory_resolver():
        return object()

    app.dependency_overrides[
        get_memory_resolver
    ] = override_memory_resolver

    response = client.post(
        "/api/memories/ingest",
        json={"text": "   "},
    )

    assert response.status_code == 422


def test_confirm_pending_memory_route(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    resolver = object()

    async def override_memory_resolver():
        return resolver

    app.dependency_overrides[
        get_memory_resolver
    ] = override_memory_resolver
    candidate = make_memory_read().model_copy(
        update={
            "status": MemoryStatus.ARCHIVED,
            "source": MemorySource.CONVERSATION,
        }
    )
    result = MemoryConfirmationResponse(candidate=candidate)
    confirm = AsyncMock(return_value=result)
    monkeypatch.setattr(
        "router.memory.confirm_memory_for_user",
        confirm,
    )

    response = client.post(
        "/api/memories/1/confirmation",
        json={"approved": False},
    )

    assert response.status_code == 200
    assert response.json()["data"]["candidate"]["status"] == (
        "archived"
    )
    confirm.assert_awaited_once_with(
        1,
        MemoryConfirmationRequest(approved=False),
        fake_user.user_id,
        fake_db,
        resolver,
    )
