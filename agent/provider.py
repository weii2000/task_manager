import logging
from typing import Protocol, TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from agent.llm import LLMRequest
from exceptions.agent import AgentProviderError, AgentResponseFormatError


ResponseT = TypeVar("ResponseT", bound=BaseModel)
logger = logging.getLogger(__name__)
MAX_INVALID_RESPONSE_LOG_LENGTH = 2000


class LLMProvider(Protocol):
    async def complete(
        self,
        request: LLMRequest,
        response_model: type[ResponseT],
    ) -> ResponseT:
        ...


class OpenAICompatibleLLMProvider:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def complete(
        self,
        request: LLMRequest,
        response_model: type[ResponseT],
    ) -> ResponseT:
        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    message.model_dump()
                    for message in request.messages
                ],  # type: ignore[arg-type]
                response_format={"type": "json_object"},
            )
            raw_content = completion.choices[0].message.content
            if raw_content is None:
                raise AgentResponseFormatError()

            try:
                return response_model.model_validate_json(raw_content)
            except ValidationError as exc:
                logger.warning(
                    "Invalid agent response format: raw_content=%r errors=%s",
                    raw_content[:MAX_INVALID_RESPONSE_LOG_LENGTH],
                    exc.errors(),
                )
                raise AgentResponseFormatError() from exc
        except AgentResponseFormatError:
            raise
        except (IndexError, AttributeError, TypeError) as exc:
            raise AgentResponseFormatError() from exc
        except OpenAIError as exc:
            raise AgentProviderError() from exc
