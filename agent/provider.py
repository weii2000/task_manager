from typing import Protocol, TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from agent.llm import LLMRequest
from exceptions.agent import AgentProviderError, AgentResponseFormatError


ResponseT = TypeVar("ResponseT", bound=BaseModel)


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
            )
            raw_content = completion.choices[0].message.content
            if raw_content is None:
                raise AgentResponseFormatError()

            return response_model.model_validate_json(raw_content)
        except AgentResponseFormatError:
            raise
        except (ValidationError, IndexError, AttributeError, TypeError) as exc:
            raise AgentResponseFormatError() from exc
        except OpenAIError as exc:
            raise AgentProviderError() from exc
