from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from agent.state import PlanningState


class PlanningTurnRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=5000,
    )
    state: PlanningState = Field(
        default_factory=PlanningState,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @model_validator(mode="after")
    def validate_context_size(self):
        messages = self.state.messages

        if len(messages) >= 30:
            raise ValueError(
                "规划对话不能超过 30 条消息"
            )

        context_size = len(self.message) + sum(
            len(message.content)
            for message in messages
        )

        if context_size > 30_000:
            raise ValueError(
                "规划对话上下文不能超过 30000 个字符"
            )

        return self
