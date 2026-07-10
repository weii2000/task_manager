from pydantic import BaseModel, Field

from agent.state import MessageRole


class LLMMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)


class LLMRequest(BaseModel):
    messages: list[LLMMessage] = Field(min_length=1)
