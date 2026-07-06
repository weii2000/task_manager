import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from openai import OpenAIError
import pytest

from agent.provider import OpenAICompatibleLLMProvider
from agent.state import Message, MessageRole, PlanningDraft, PlanningInfo, ResponseMessage, State
from exceptions.agent import AgentProviderError, AgentResponseFormatError


def make_provider_with_response(content: str | None) -> OpenAICompatibleLLMProvider:
    provider = OpenAICompatibleLLMProvider(
        api_key="test-api-key",
        base_url="https://example.com/v1",
        model="test-model",
    )
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
    )
    provider._client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(return_value=completion),
            ),
        ),
    )
    return provider


def make_state() -> State:
    return State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        info=PlanningInfo(),
        draft=PlanningDraft(),
    )


def test_provider_rejects_non_json_response():
    provider = make_provider_with_response("不是 JSON")

    with pytest.raises(AgentResponseFormatError):
        asyncio.run(provider.complete(make_state()))


def test_provider_rejects_empty_response_content():
    provider = make_provider_with_response(None)

    with pytest.raises(AgentResponseFormatError):
        asyncio.run(provider.complete(make_state()))


def test_provider_parses_valid_response():
    provider = make_provider_with_response(
        """
        {
          "content": "你的目标是什么？",
          "next_action": "clarify",
          "tool_calls": [],
          "info": {
            "goal": null,
            "acceptance_criteria": null,
            "constraints": null
          },
          "draft": {
            "tasks": []
          }
        }
        """
    )

    result = asyncio.run(provider.complete(make_state()))

    assert isinstance(result.messages[-1], ResponseMessage)
    assert result.messages[-1].content == "你的目标是什么？"
    assert result.messages[-1].next_action == "clarify"


def test_provider_converts_openai_error():
    provider = make_provider_with_response("{}")
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[union-attr]
        side_effect=OpenAIError("provider unavailable"),
    )

    with pytest.raises(AgentProviderError):
        asyncio.run(provider.complete(make_state()))
