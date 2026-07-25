import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import OpenAIError

from agent.provider import LLMMessage, LLMRequest, OpenAICompatibleLLMProvider
from agent.runtime.state import Action, PlanDecision
from exceptions.agent import AgentProviderError, AgentResponseFormatError


def make_completion(content: str | None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
    )


def make_provider_with_response(
    content: str | None,
    max_format_attempts: int = 2,
) -> OpenAICompatibleLLMProvider:
    provider = OpenAICompatibleLLMProvider(
        api_key="test-api-key",
        base_url="https://example.com/v1",
        model="test-model",
        max_format_attempts=max_format_attempts,
    )
    provider._client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(return_value=make_completion(content)),
            ),
        ),
    )
    return provider


def make_request() -> LLMRequest:
    return LLMRequest(
        messages=[LLMMessage(role="user", content="帮我规划学习")]
    )


def test_provider_rejects_non_json_response():
    provider = make_provider_with_response("不是 JSON")

    with pytest.raises(AgentResponseFormatError):
        asyncio.run(provider.complete(make_request(), PlanDecision))

    assert provider._client.chat.completions.create.await_count == 2


def test_provider_rejects_empty_response_content():
    provider = make_provider_with_response(None)

    with pytest.raises(AgentResponseFormatError):
        asyncio.run(provider.complete(make_request(), PlanDecision))

    assert provider._client.chat.completions.create.await_count == 2


def test_provider_recovers_from_invalid_json_with_one_format_retry():
    provider = make_provider_with_response("不是 JSON")
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[union-attr]
        side_effect=[
            make_completion("不是 JSON"),
            make_completion(
                """
                {
                  "content": "你的目标是什么？",
                  "next_action": "clarify",
                  "tool_calls": []
                }
                """
            ),
        ]
    )

    result = asyncio.run(provider.complete(make_request(), PlanDecision))

    assert result.next_action == Action.CLARIFY
    assert provider._client.chat.completions.create.await_count == 2
    retry_messages = (
        provider._client.chat.completions.create.await_args_list[1]
        .kwargs["messages"]
    )
    assert retry_messages[-1]["role"] == "system"
    assert "严格合法的 JSON" in retry_messages[-1]["content"]


def test_provider_does_not_log_invalid_raw_content(caplog):
    provider = make_provider_with_response(
        "SENSITIVE_INVALID_CONTENT //",
        max_format_attempts=1,
    )

    with pytest.raises(AgentResponseFormatError):
        asyncio.run(provider.complete(make_request(), PlanDecision))

    assert "SENSITIVE_INVALID_CONTENT" not in caplog.text
    assert "content_length=" in caplog.text


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

    result = asyncio.run(provider.complete(make_request(), PlanDecision))

    assert isinstance(result, PlanDecision)
    assert result.content == "你的目标是什么？"
    assert result.next_action == Action.CLARIFY
    assert (
        provider._client.chat.completions.create.await_args.kwargs[
            "response_format"
        ]
        == {"type": "json_object"}
    )


def test_provider_accepts_response_without_optional_state_fields():
    provider = make_provider_with_response(
        """
        {
          "content": "你的目标是什么？",
          "next_action": "clarify",
          "tool_calls": []
        }
        """
    )

    result = asyncio.run(provider.complete(make_request(), PlanDecision))

    assert result.info.goal is None
    assert result.draft.tasks == []


def test_provider_converts_openai_error():
    provider = make_provider_with_response("{}")
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[union-attr]
        side_effect=OpenAIError("provider unavailable"),
    )

    with pytest.raises(AgentProviderError):
        asyncio.run(provider.complete(make_request(), PlanDecision))

    assert provider._client.chat.completions.create.await_count == 1


def test_provider_rejects_invalid_format_attempt_limit():
    with pytest.raises(ValueError):
        OpenAICompatibleLLMProvider(
            api_key="test-api-key",
            base_url="https://example.com/v1",
            model="test-model",
            max_format_attempts=0,
        )
