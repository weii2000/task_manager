import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.long_term_memory import (
    MemoryResolutionResult,
    MemoryWriteAction,
    MemoryWriteOperation,
)
from agent.memory_extractor import (
    ExtractedMemoryCandidate,
    MemoryExtractionResult,
)
from agent.state import Message, MessageRole
from exceptions.memory import (
    ArchivedMemoryModificationError,
    MemoryStateConflictError,
)
from models.enums import (
    MemoryCategory,
    MemorySource,
    MemoryStatus,
)
from schemas.memory import (
    MemoryConfirmationRequest,
    MemoryIngestRequest,
    MemoryUpdateRequest,
)
from services import memory as memory_service


def make_db_with_transaction():
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    db = MagicMock()
    db.begin.return_value = transaction
    return db


def make_memory(
    memory_id: int,
    *,
    content: str = "用户偏好短任务",
    version: int = 1,
) -> SimpleNamespace:
    now = datetime(2026, 7, 13, 10)
    return SimpleNamespace(
        memory_id=memory_id,
        user_id=1,
        category=MemoryCategory.PREFERENCE,
        content=content,
        status=MemoryStatus.ACTIVE,
        source=MemorySource.MANUAL,
        source_agent_session_id=None,
        source_message_index=None,
        version=version,
        created_time=now,
        updated_time=now,
    )


def test_ingest_memory_applies_create_update_and_ignore(monkeypatch):
    existing = make_memory(1)
    created_memory = make_memory(
        2,
        content="用户长期目标是成为 Agent 工程师",
    )
    created_memory.category = MemoryCategory.LONG_TERM_GOAL
    resolver = SimpleNamespace(
        resolve=AsyncMock(
            return_value=MemoryResolutionResult(
                operations=[
                    MemoryWriteOperation(
                        action=MemoryWriteAction.UPDATE,
                        target_memory_id=1,
                        category=MemoryCategory.PREFERENCE,
                        content="用户偏好一小时以内的任务",
                    ),
                    MemoryWriteOperation(
                        action=MemoryWriteAction.CREATE,
                        category=MemoryCategory.LONG_TERM_GOAL,
                        content="用户长期目标是成为 Agent 工程师",
                    ),
                    MemoryWriteOperation(
                        action=MemoryWriteAction.IGNORE,
                        target_memory_id=1,
                    ),
                ]
            )
        )
    )
    get_memories = AsyncMock(side_effect=[[existing], [existing]])
    monkeypatch.setattr(
        memory_service,
        "get_memories_by_user_id_and_status",
        get_memories,
    )
    monkeypatch.setattr(
        memory_service,
        "lock_user_for_memory_update",
        AsyncMock(return_value=SimpleNamespace(user_id=1)),
    )
    monkeypatch.setattr(
        memory_service,
        "create_memory_by_data",
        AsyncMock(return_value=created_memory),
    )

    async def update_memory(memory, update_data, db):
        for field, value in update_data.items():
            setattr(memory, field, value)
        return memory

    monkeypatch.setattr(
        memory_service,
        "update_memory_by_data",
        AsyncMock(side_effect=update_memory),
    )
    db = make_db_with_transaction()

    result = asyncio.run(
        memory_service.ingest_memories_for_user(
            MemoryIngestRequest(
                text="任务一小时以内，长期目标是 Agent 工程师"
            ),
            user_id=1,
            db=db,
            resolver=resolver,
        )
    )

    assert [memory.memory_id for memory in result.created] == [2]
    assert [memory.memory_id for memory in result.updated] == [1]
    assert result.updated[0].version == 2
    assert result.ignored_count == 1
    existing_arg = resolver.resolve.await_args.args[1][0]
    assert existing_arg.memory_id == 1
    assert existing_arg.version == 1


def test_ingest_memory_rejects_stale_snapshot(monkeypatch):
    initial = make_memory(1, version=1)
    current = make_memory(1, version=2)
    resolver = SimpleNamespace(
        resolve=AsyncMock(
            return_value=MemoryResolutionResult(
                operations=[
                    MemoryWriteOperation(
                        action=MemoryWriteAction.UPDATE,
                        target_memory_id=1,
                        category=MemoryCategory.PREFERENCE,
                        content="更新后的偏好",
                    )
                ]
            )
        )
    )
    monkeypatch.setattr(
        memory_service,
        "get_memories_by_user_id_and_status",
        AsyncMock(side_effect=[[initial], [current]]),
    )
    monkeypatch.setattr(
        memory_service,
        "lock_user_for_memory_update",
        AsyncMock(return_value=SimpleNamespace(user_id=1)),
    )
    create_memory = AsyncMock()
    update_memory = AsyncMock()
    monkeypatch.setattr(
        memory_service,
        "create_memory_by_data",
        create_memory,
    )
    monkeypatch.setattr(
        memory_service,
        "update_memory_by_data",
        update_memory,
    )

    with pytest.raises(MemoryStateConflictError):
        asyncio.run(
            memory_service.ingest_memories_for_user(
                MemoryIngestRequest(text="更新偏好"),
                user_id=1,
                db=make_db_with_transaction(),
                resolver=resolver,
            )
        )

    create_memory.assert_not_awaited()
    update_memory.assert_not_awaited()


def test_active_memory_references_are_limited_and_transport_safe(
    monkeypatch,
):
    get_memories = AsyncMock(return_value=[make_memory(1)])
    monkeypatch.setattr(
        memory_service,
        "get_memories_by_user_id_and_status",
        get_memories,
    )
    db = MagicMock()

    result = asyncio.run(
        memory_service.get_active_memory_references_for_user(
            user_id=1,
            db=db,
            limit=10,
        )
    )

    assert result[0].model_dump(mode="json") == {
        "memory_id": 1,
        "category": "preference",
        "content": "用户偏好短任务",
    }
    get_memories.assert_awaited_once_with(
        1,
        MemoryStatus.ACTIVE,
        db,
        limit=10,
    )


def test_update_memory_rejects_archived_record(monkeypatch):
    memory = make_memory(1)
    memory.status = MemoryStatus.ARCHIVED
    get_memory = AsyncMock(return_value=memory)
    update_memory = AsyncMock()
    monkeypatch.setattr(
        memory_service,
        "get_memory_by_id_and_user_id",
        get_memory,
    )
    monkeypatch.setattr(
        memory_service,
        "update_memory_by_data",
        update_memory,
    )
    db = make_db_with_transaction()

    with pytest.raises(ArchivedMemoryModificationError):
        asyncio.run(
            memory_service.update_memory_for_user(
                memory_id=1,
                request=MemoryUpdateRequest(content="新内容"),
                user_id=7,
                db=db,
            )
        )

    get_memory.assert_awaited_once_with(
        1,
        7,
        db,
        for_update=True,
    )
    update_memory.assert_not_awaited()


def test_archive_memory_is_idempotent(monkeypatch):
    memory = make_memory(1)
    get_memory = AsyncMock(return_value=memory)

    async def update_memory(record, update_data, db):
        for field, value in update_data.items():
            setattr(record, field, value)
        return record

    update = AsyncMock(side_effect=update_memory)
    monkeypatch.setattr(
        memory_service,
        "get_memory_by_id_and_user_id",
        get_memory,
    )
    monkeypatch.setattr(
        memory_service,
        "update_memory_by_data",
        update,
    )
    db = make_db_with_transaction()

    first = asyncio.run(
        memory_service.archive_memory_for_user(1, 1, db)
    )
    second = asyncio.run(
        memory_service.archive_memory_for_user(1, 1, db)
    )

    assert first.status == MemoryStatus.ARCHIVED
    assert second.status == MemoryStatus.ARCHIVED
    assert first.version == 2
    update.assert_awaited_once()


def test_extracted_memories_are_saved_as_deduplicated_pending_records(
    monkeypatch,
):
    active = make_memory(1, content="用户偏好短任务")
    pending = make_memory(
        2,
        content="用户长期目标是成为 Agent 工程师",
    )
    pending.category = MemoryCategory.LONG_TERM_GOAL
    pending.status = MemoryStatus.PENDING
    pending.source = MemorySource.CONVERSATION
    pending.source_agent_session_id = 9
    pending.source_message_index = 3
    extractor = SimpleNamespace(
        extract=AsyncMock(
            return_value=MemoryExtractionResult(
                candidates=[
                    ExtractedMemoryCandidate(
                        category=MemoryCategory.PREFERENCE,
                        content=" 用户偏好短任务 ",
                        evidence="我喜欢短任务",
                    ),
                    ExtractedMemoryCandidate(
                        category=MemoryCategory.LONG_TERM_GOAL,
                        content="用户长期目标是成为 Agent 工程师",
                        evidence="我想成为 Agent 工程师",
                    ),
                    ExtractedMemoryCandidate(
                        category=MemoryCategory.LONG_TERM_GOAL,
                        content="用户长期目标是成为 Agent 工程师",
                        evidence="长期目标就是这个",
                    ),
                ]
            )
        )
    )
    monkeypatch.setattr(
        memory_service,
        "lock_user_for_memory_update",
        AsyncMock(return_value=SimpleNamespace(user_id=1)),
    )
    monkeypatch.setattr(
        memory_service,
        "get_memories_by_user_id_and_status",
        AsyncMock(side_effect=[[active], []]),
    )
    create = AsyncMock(return_value=pending)
    monkeypatch.setattr(
        memory_service,
        "create_memory_by_data",
        create,
    )
    messages = [
        Message(role=MessageRole.USER, content="我喜欢短任务"),
        Message(
            role=MessageRole.USER,
            content="我想成为 Agent 工程师",
        ),
    ]

    result = asyncio.run(
        memory_service.extract_pending_memories_from_turn(
            messages=messages,
            source_message_index=3,
            session_id=9,
            user_id=1,
            db=make_db_with_transaction(),
            extractor=extractor,
        )
    )

    assert [memory.memory_id for memory in result] == [2]
    create.assert_awaited_once()
    create_data = create.await_args.args[0]
    assert create_data["status"] == MemoryStatus.PENDING
    assert create_data["source"] == MemorySource.CONVERSATION
    assert create_data["source_agent_session_id"] == 9
    assert create_data["source_message_index"] == 3


def test_approved_pending_memory_updates_active_memory(monkeypatch):
    active = make_memory(1, content="用户偏好短任务")
    candidate = make_memory(
        2,
        content="用户偏好每个任务不超过一小时",
    )
    candidate.status = MemoryStatus.PENDING
    candidate.source = MemorySource.CONVERSATION
    candidate.source_agent_session_id = 9
    candidate.source_message_index = 3
    resolver = SimpleNamespace(
        resolve=AsyncMock(
            return_value=MemoryResolutionResult(
                operations=[
                    MemoryWriteOperation(
                        action=MemoryWriteAction.UPDATE,
                        target_memory_id=1,
                        category=MemoryCategory.PREFERENCE,
                        content="用户偏好每个任务不超过一小时",
                    )
                ]
            )
        )
    )
    monkeypatch.setattr(
        memory_service,
        "get_memory_by_id_and_user_id",
        AsyncMock(side_effect=[candidate, candidate]),
    )
    monkeypatch.setattr(
        memory_service,
        "get_memories_by_user_id_and_status",
        AsyncMock(side_effect=[[active], [active]]),
    )
    monkeypatch.setattr(
        memory_service,
        "lock_user_for_memory_update",
        AsyncMock(return_value=SimpleNamespace(user_id=1)),
    )

    async def update_memory(record, update_data, db):
        for field, value in update_data.items():
            setattr(record, field, value)
        return record

    update = AsyncMock(side_effect=update_memory)
    monkeypatch.setattr(
        memory_service,
        "update_memory_by_data",
        update,
    )

    result = asyncio.run(
        memory_service.confirm_memory_for_user(
            memory_id=2,
            request=MemoryConfirmationRequest(approved=True),
            user_id=1,
            db=make_db_with_transaction(),
            resolver=resolver,
        )
    )

    assert result.candidate.status == MemoryStatus.ARCHIVED
    assert result.updated[0].memory_id == 1
    assert result.updated[0].source == MemorySource.CONVERSATION
    assert result.updated[0].source_agent_session_id == 9
    assert result.updated[0].source_message_index == 3
    assert result.updated[0].version == 2
    assert update.await_count == 2


def test_rejected_pending_memory_is_archived_without_llm(monkeypatch):
    candidate = make_memory(2, content="候选记忆")
    candidate.status = MemoryStatus.PENDING
    candidate.source = MemorySource.CONVERSATION
    resolver = SimpleNamespace(resolve=AsyncMock())
    monkeypatch.setattr(
        memory_service,
        "get_memory_by_id_and_user_id",
        AsyncMock(return_value=candidate),
    )

    async def update_memory(record, update_data, db):
        for field, value in update_data.items():
            setattr(record, field, value)
        return record

    monkeypatch.setattr(
        memory_service,
        "update_memory_by_data",
        AsyncMock(side_effect=update_memory),
    )

    result = asyncio.run(
        memory_service.confirm_memory_for_user(
            memory_id=2,
            request=MemoryConfirmationRequest(approved=False),
            user_id=1,
            db=make_db_with_transaction(),
            resolver=resolver,
        )
    )

    assert result.candidate.status == MemoryStatus.ARCHIVED
    assert result.candidate.version == 2
    resolver.resolve.assert_not_awaited()
