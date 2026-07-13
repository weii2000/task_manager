import logging
from typing import Protocol, TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

from agent.state import MessageRole
from exceptions.agent import AgentProviderError, AgentResponseFormatError


ResponseT = TypeVar("ResponseT", bound=BaseModel)
logger = logging.getLogger(__name__)

FORMAT_RETRY_SYSTEM_PROMPT = """
上一次响应未通过格式校验。请重新完成相同任务，并且只返回一个严格合法的 JSON 对象。
禁止输出注释、Markdown、额外文本、重复字段或拼错的字段；所有字段必须严格符合原系统提示定义的结构。
""".strip()


class LLMMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)


class LLMRequest(BaseModel):
    messages: list[LLMMessage] = Field(min_length=1)


class LLMProvider(Protocol):
    async def complete(
        self,
        request: LLMRequest,
        response_model: type[ResponseT],
    ) -> ResponseT:
        ...


class OpenAICompatibleLLMProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_format_attempts: int = 2,
    ) -> None:
        if max_format_attempts < 1:
            raise ValueError("max format attempts must be at least 1")
        self._model = model
        self._max_format_attempts = max_format_attempts
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def complete(
        self,
        request: LLMRequest,
        response_model: type[ResponseT],
    ) -> ResponseT:
        messages = request.messages
        for attempt in range(1, self._max_format_attempts + 1):
            try:
                completion = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        message.model_dump() for message in messages
                    ],  # type: ignore[arg-type]
                    response_format={"type": "json_object"},
                )
            except OpenAIError as exc:
                raise AgentProviderError() from exc

            raw_content: str | None = None
            error_detail: object
            try:
                raw_content = completion.choices[0].message.content
                if raw_content is None:
                    raise AgentResponseFormatError()
                result = response_model.model_validate_json(raw_content)
            except ValidationError as exc:
                format_error: Exception = exc
                error_detail = [
                    {
                        "type": error["type"],
                        "loc": error["loc"],
                        "msg": error["msg"],
                    }
                    for error in exc.errors()
                ]
            except (
                AgentResponseFormatError,
                IndexError,
                AttributeError,
                TypeError,
            ) as exc:
                format_error = exc
                error_detail = type(exc).__name__
            else:
                if attempt > 1:
                    logger.info(
                        "Agent response format recovered after retry: "
                        "attempt=%s",
                        attempt,
                    )
                return result

            logger.warning(
                "Invalid agent response format: attempt=%s/%s "
                "content_length=%s errors=%s",
                attempt,
                self._max_format_attempts,
                len(raw_content) if raw_content is not None else None,
                error_detail,
            )
            if attempt == self._max_format_attempts:
                raise AgentResponseFormatError() from format_error

            messages = [
                *request.messages,
                LLMMessage(
                    role=MessageRole.SYSTEM,
                    content=FORMAT_RETRY_SYSTEM_PROMPT,
                ),
            ]

        raise AgentResponseFormatError()
