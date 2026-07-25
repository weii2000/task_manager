import asyncio
import json
from unittest.mock import AsyncMock

from agent.memory.extraction import (
    ExtractedMemoryCandidate,
    LLMMemoryExtractor,
    MemoryExtractionResult,
)
from agent.runtime.state import Message, MessageRole
from models.enums import MemoryCategory


def test_memory_extractor_uses_recent_dialogue_as_untrusted_data():
    provider = AsyncMock()
    extraction = MemoryExtractionResult(
        candidates=[
            ExtractedMemoryCandidate(
                category=MemoryCategory.PREFERENCE,
                content="用户偏好每个任务不超过一小时",
                evidence="以后任务尽量都不要超过一小时",
            )
        ]
    )
    provider.complete = AsyncMock(return_value=extraction)
    extractor = LLMMemoryExtractor(provider)
    messages = [
        Message(
            role=MessageRole.ASSISTANT,
            content="你对任务粒度有什么偏好吗？",
        ),
        Message(
            role=MessageRole.USER,
            content="以后任务尽量都不要超过一小时",
        ),
    ]

    result = asyncio.run(extractor.extract(messages))

    assert result == extraction
    request = provider.complete.await_args.args[0]
    payload = json.loads(request.messages[1].content)
    assert payload["messages"] == [
        {
            "role": "assistant",
            "content": "你对任务粒度有什么偏好吗？",
        },
        {
            "role": "user",
            "content": "以后任务尽量都不要超过一小时",
        },
    ]


def test_memory_extractor_can_return_no_candidates():
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=MemoryExtractionResult()
    )
    extractor = LLMMemoryExtractor(provider)

    result = asyncio.run(
        extractor.extract(
            [Message(role=MessageRole.USER, content="你好")]
        )
    )

    assert result.candidates == []
