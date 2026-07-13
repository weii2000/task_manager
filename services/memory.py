from sqlalchemy.ext.asyncio import AsyncSession

from agent.context import RetrievedMemory
from agent.long_term_memory import (
    ExistingMemory,
    MemoryResolutionResult,
    MemoryResolver,
    MemoryWriteAction,
)
from agent.memory_extractor import MemoryExtractor
from agent.state import Message
from crud.memory import (
    create_memory_by_data,
    get_memories_by_user_id_and_status,
    get_memory_by_id_and_user_id,
    lock_user_for_memory_update,
    update_memory_by_data,
)
from exceptions.memory import (
    ArchivedMemoryModificationError,
    MemoryNotFoundError,
    MemoryNotPendingError,
    MemoryResolutionError,
    MemoryStateConflictError,
)
from exceptions.user import UserNotFoundError
from models.enums import MemoryCategory, MemorySource, MemoryStatus
from models.memory import UserMemory
from schemas.memory import (
    MemoryConfirmationRequest,
    MemoryConfirmationResponse,
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryRead,
    MemoryUpdateRequest,
)


AGENT_MEMORY_LIMIT = 30


def _to_existing_memory(memory: UserMemory) -> ExistingMemory:
    return ExistingMemory(
        memory_id=memory.memory_id,
        category=memory.category,
        content=memory.content,
        version=memory.version,
    )


def _memory_fingerprint(
    memories: list[UserMemory],
) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            (memory.memory_id, memory.version)
            for memory in memories
        )
    )


def _candidate_fingerprint(memory: UserMemory) -> tuple[object, ...]:
    return (
        memory.memory_id,
        memory.version,
        memory.status,
        memory.category,
        memory.content,
        memory.source,
        memory.source_agent_session_id,
        memory.source_message_index,
    )


def _normalized_memory_key(
    category: MemoryCategory,
    content: str,
) -> tuple[MemoryCategory, str]:
    normalized_content = " ".join(content.split()).casefold()
    return category, normalized_content


async def _apply_resolution_locked(
    resolution: MemoryResolutionResult,
    user_id: int,
    current_models: list[UserMemory],
    source: MemorySource,
    source_agent_session_id: int | None,
    source_message_index: int | None,
    db: AsyncSession,
) -> tuple[list[UserMemory], list[UserMemory], int]:
    created: list[UserMemory] = []
    updated: list[UserMemory] = []
    ignored_count = 0
    current_by_id = {
        memory.memory_id: memory for memory in current_models
    }
    known_keys = {
        _normalized_memory_key(memory.category, memory.content): (
            memory.memory_id
        )
        for memory in current_models
    }
    updated_target_ids: set[int] = set()

    for operation in resolution.operations:
        if operation.action == MemoryWriteAction.IGNORE:
            ignored_count += 1
            continue

        if operation.category is None or operation.content is None:
            raise MemoryResolutionError()

        operation_key = _normalized_memory_key(
            operation.category,
            operation.content,
        )

        if operation.action == MemoryWriteAction.CREATE:
            if operation_key in known_keys:
                ignored_count += 1
                continue
            memory = await create_memory_by_data(
                {
                    "user_id": user_id,
                    "category": operation.category,
                    "content": operation.content,
                    "status": MemoryStatus.ACTIVE,
                    "source": source,
                    "source_agent_session_id": (
                        source_agent_session_id
                    ),
                    "source_message_index": source_message_index,
                    "version": 1,
                },
                db,
            )
            created.append(memory)
            known_keys[operation_key] = memory.memory_id
            continue

        target_id = operation.target_memory_id
        if target_id is None or target_id in updated_target_ids:
            raise MemoryResolutionError()
        updated_target_ids.add(target_id)

        target = current_by_id.get(target_id)
        if target is None:
            raise MemoryStateConflictError()
        duplicate_id = known_keys.get(operation_key)
        if duplicate_id is not None:
            ignored_count += 1
            continue

        old_key = _normalized_memory_key(
            target.category,
            target.content,
        )
        known_keys.pop(old_key, None)
        memory = await update_memory_by_data(
            target,
            {
                "category": operation.category,
                "content": operation.content,
                "source": source,
                "source_agent_session_id": source_agent_session_id,
                "source_message_index": source_message_index,
                "version": target.version + 1,
            },
            db,
        )
        updated.append(memory)
        known_keys[operation_key] = memory.memory_id

    return created, updated, ignored_count


async def ingest_memories_for_user(
    request: MemoryIngestRequest,
    user_id: int,
    db: AsyncSession,
    resolver: MemoryResolver,
) -> MemoryIngestResponse:
    async with db.begin():
        existing_models = await get_memories_by_user_id_and_status(
            user_id,
            MemoryStatus.ACTIVE,
            db,
        )

    existing_memories = [
        _to_existing_memory(memory) for memory in existing_models
    ]
    resolution = await resolver.resolve(
        request.text,
        existing_memories,
    )
    if not resolution.operations:
        return MemoryIngestResponse(ignored_count=1)

    snapshot = _memory_fingerprint(existing_models)
    async with db.begin():
        user = await lock_user_for_memory_update(user_id, db)
        if user is None:
            raise UserNotFoundError()

        current_models = await get_memories_by_user_id_and_status(
            user_id,
            MemoryStatus.ACTIVE,
            db,
            for_update=True,
        )
        if _memory_fingerprint(current_models) != snapshot:
            raise MemoryStateConflictError()

        created, updated, ignored_count = (
            await _apply_resolution_locked(
                resolution,
                user_id,
                current_models,
                MemorySource.MANUAL,
                None,
                None,
                db,
            )
        )

    return MemoryIngestResponse(
        created=[MemoryRead.model_validate(memory) for memory in created],
        updated=[MemoryRead.model_validate(memory) for memory in updated],
        ignored_count=ignored_count,
    )


async def extract_pending_memories_from_turn(
    messages: list[Message],
    source_message_index: int,
    session_id: int,
    user_id: int,
    db: AsyncSession,
    extractor: MemoryExtractor,
) -> list[MemoryRead]:
    result = await extractor.extract(messages)
    if not result.candidates:
        return []

    created: list[UserMemory] = []
    async with db.begin():
        user = await lock_user_for_memory_update(user_id, db)
        if user is None:
            raise UserNotFoundError()

        active_memories = await get_memories_by_user_id_and_status(
            user_id,
            MemoryStatus.ACTIVE,
            db,
            for_update=True,
        )
        pending_memories = await get_memories_by_user_id_and_status(
            user_id,
            MemoryStatus.PENDING,
            db,
            for_update=True,
        )
        known_keys = {
            _normalized_memory_key(memory.category, memory.content)
            for memory in [*active_memories, *pending_memories]
        }

        for candidate in result.candidates:
            key = _normalized_memory_key(
                candidate.category,
                candidate.content,
            )
            if key in known_keys:
                continue

            memory = await create_memory_by_data(
                {
                    "user_id": user_id,
                    "category": candidate.category,
                    "content": candidate.content,
                    "status": MemoryStatus.PENDING,
                    "source": MemorySource.CONVERSATION,
                    "source_agent_session_id": session_id,
                    "source_message_index": source_message_index,
                    "version": 1,
                },
                db,
            )
            created.append(memory)
            known_keys.add(key)

    return [MemoryRead.model_validate(memory) for memory in created]


async def confirm_memory_for_user(
    memory_id: int,
    request: MemoryConfirmationRequest,
    user_id: int,
    db: AsyncSession,
    resolver: MemoryResolver,
) -> MemoryConfirmationResponse:
    if not request.approved:
        return await _reject_pending_memory_for_user(
            memory_id,
            user_id,
            db,
        )

    async with db.begin():
        candidate = await get_memory_by_id_and_user_id(
            memory_id,
            user_id,
            db,
        )
        if candidate is None:
            raise MemoryNotFoundError()
        if candidate.status != MemoryStatus.PENDING:
            raise MemoryNotPendingError()
        active_models = await get_memories_by_user_id_and_status(
            user_id,
            MemoryStatus.ACTIVE,
            db,
        )

    candidate_snapshot = _candidate_fingerprint(candidate)
    active_snapshot = _memory_fingerprint(active_models)
    resolution = await resolver.resolve(
        candidate.content,
        [_to_existing_memory(memory) for memory in active_models],
    )

    async with db.begin():
        user = await lock_user_for_memory_update(user_id, db)
        if user is None:
            raise UserNotFoundError()

        current_candidate = await get_memory_by_id_and_user_id(
            memory_id,
            user_id,
            db,
            for_update=True,
        )
        if current_candidate is None:
            raise MemoryNotFoundError()
        if _candidate_fingerprint(current_candidate) != candidate_snapshot:
            raise MemoryStateConflictError()

        current_active = await get_memories_by_user_id_and_status(
            user_id,
            MemoryStatus.ACTIVE,
            db,
            for_update=True,
        )
        if _memory_fingerprint(current_active) != active_snapshot:
            raise MemoryStateConflictError()

        created, updated, ignored_count = (
            await _apply_resolution_locked(
                resolution,
                user_id,
                current_active,
                current_candidate.source,
                current_candidate.source_agent_session_id,
                current_candidate.source_message_index,
                db,
            )
        )
        if not resolution.operations:
            ignored_count = 1
        current_candidate = await update_memory_by_data(
            current_candidate,
            {
                "status": MemoryStatus.ARCHIVED,
                "version": current_candidate.version + 1,
            },
            db,
        )

    return MemoryConfirmationResponse(
        candidate=MemoryRead.model_validate(current_candidate),
        created=[MemoryRead.model_validate(memory) for memory in created],
        updated=[MemoryRead.model_validate(memory) for memory in updated],
        ignored_count=ignored_count,
    )


async def _reject_pending_memory_for_user(
    memory_id: int,
    user_id: int,
    db: AsyncSession,
) -> MemoryConfirmationResponse:
    async with db.begin():
        candidate = await get_memory_by_id_and_user_id(
            memory_id,
            user_id,
            db,
            for_update=True,
        )
        if candidate is None:
            raise MemoryNotFoundError()
        if candidate.status != MemoryStatus.PENDING:
            raise MemoryNotPendingError()
        candidate = await update_memory_by_data(
            candidate,
            {
                "status": MemoryStatus.ARCHIVED,
                "version": candidate.version + 1,
            },
            db,
        )

    return MemoryConfirmationResponse(
        candidate=MemoryRead.model_validate(candidate)
    )


async def get_memories_for_user(
    user_id: int,
    status: MemoryStatus,
    db: AsyncSession,
) -> list[MemoryRead]:
    async with db.begin():
        memories = await get_memories_by_user_id_and_status(
            user_id,
            status,
            db,
        )
    return [MemoryRead.model_validate(memory) for memory in memories]


async def get_active_memory_references_for_user(
    user_id: int,
    db: AsyncSession,
    limit: int = AGENT_MEMORY_LIMIT,
) -> list[RetrievedMemory]:
    memories = await get_memories_by_user_id_and_status(
        user_id,
        MemoryStatus.ACTIVE,
        db,
        limit=limit,
    )
    return [
        RetrievedMemory(
            memory_id=memory.memory_id,
            category=memory.category,
            content=memory.content,
        )
        for memory in memories
    ]


async def update_memory_for_user(
    memory_id: int,
    request: MemoryUpdateRequest,
    user_id: int,
    db: AsyncSession,
) -> MemoryRead:
    async with db.begin():
        memory = await get_memory_by_id_and_user_id(
            memory_id,
            user_id,
            db,
            for_update=True,
        )
        if memory is None:
            raise MemoryNotFoundError()
        if memory.status == MemoryStatus.ARCHIVED:
            raise ArchivedMemoryModificationError()

        update_data = request.model_dump(exclude_unset=True)
        update_data["source"] = MemorySource.MANUAL
        update_data["source_agent_session_id"] = None
        update_data["source_message_index"] = None
        update_data["version"] = memory.version + 1
        memory = await update_memory_by_data(
            memory,
            update_data,
            db,
        )

    return MemoryRead.model_validate(memory)


async def archive_memory_for_user(
    memory_id: int,
    user_id: int,
    db: AsyncSession,
) -> MemoryRead:
    async with db.begin():
        memory = await get_memory_by_id_and_user_id(
            memory_id,
            user_id,
            db,
            for_update=True,
        )
        if memory is None:
            raise MemoryNotFoundError()
        if memory.status != MemoryStatus.ARCHIVED:
            memory = await update_memory_by_data(
                memory,
                {
                    "status": MemoryStatus.ARCHIVED,
                    "version": memory.version + 1,
                },
                db,
            )

    return MemoryRead.model_validate(memory)
