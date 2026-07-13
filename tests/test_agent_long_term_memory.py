import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from agent.long_term_memory import (
    ExistingMemory,
    LLMMemoryResolver,
    MemoryResolutionResult,
    MemoryWriteAction,
    MemoryWriteOperation,
)
from exceptions.memory import MemoryResolutionError
from models.enums import MemoryCategory


def make_existing_memory(memory_id: int = 1) -> ExistingMemory:
    return ExistingMemory(
        memory_id=memory_id,
        category=MemoryCategory.PREFERENCE,
        content="用户偏好短任务",
        version=1,
    )


def test_llm_memory_resolver_builds_request_and_returns_operations():
    provider = AsyncMock()
    resolution = MemoryResolutionResult(
        operations=[
            MemoryWriteOperation(
                action=MemoryWriteAction.UPDATE,
                target_memory_id=1,
                category=MemoryCategory.PREFERENCE,
                content="用户偏好一小时以内的任务",
            )
        ]
    )
    provider.complete = AsyncMock(return_value=resolution)
    resolver = LLMMemoryResolver(provider)
    existing = make_existing_memory()

    result = asyncio.run(
        resolver.resolve("任务可以放宽到一小时", [existing])
    )

    assert result == resolution
    request = provider.complete.await_args.args[0]
    payload = json.loads(request.messages[1].content)
    assert payload["new_text"] == "任务可以放宽到一小时"
    assert payload["existing_memories"] == [
        {
            "memory_id": 1,
            "category": "preference",
            "content": "用户偏好短任务",
            "version": 1,
        }
    ]


def test_llm_memory_resolver_rejects_unknown_update_target():
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=MemoryResolutionResult(
            operations=[
                MemoryWriteOperation(
                    action=MemoryWriteAction.UPDATE,
                    target_memory_id=999,
                    category=MemoryCategory.PREFERENCE,
                    content="新偏好",
                )
            ]
        )
    )
    resolver = LLMMemoryResolver(provider)

    with pytest.raises(MemoryResolutionError):
        asyncio.run(
            resolver.resolve("更新偏好", [make_existing_memory()])
        )


def test_llm_memory_resolver_rejects_duplicate_updates():
    operation = MemoryWriteOperation(
        action=MemoryWriteAction.UPDATE,
        target_memory_id=1,
        category=MemoryCategory.PREFERENCE,
        content="新偏好",
    )
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=MemoryResolutionResult(
            operations=[operation, operation.model_copy()]
        )
    )
    resolver = LLMMemoryResolver(provider)

    with pytest.raises(MemoryResolutionError):
        asyncio.run(
            resolver.resolve("更新偏好", [make_existing_memory()])
        )


def test_memory_write_operation_validates_action_fields():
    with pytest.raises(ValidationError):
        MemoryWriteOperation(
            action=MemoryWriteAction.CREATE,
            target_memory_id=1,
            category=MemoryCategory.PROFILE,
            content="用户从事后端开发",
        )

    with pytest.raises(ValidationError):
        MemoryWriteOperation(action=MemoryWriteAction.UPDATE)
