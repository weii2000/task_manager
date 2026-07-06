from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class PlanningMessage(BaseModel):
    role: MessageRole
    content: str = Field(
        min_length=1,
        max_length=5000,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class PlanningInfo(BaseModel):
    goal: str | None = Field(
        default=None,
        max_length=2000,
    )
    constraints: list[str] | None = Field(
        default=None,
        max_length=20,
    )
    completion_criteria: list[str] | None = Field(
        default=None,
        max_length=20,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class PlanningPhase(StrEnum):
    CLARIFYING = "clarifying"
    DRAFT_READY = "draft_ready"


class DraftTask(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
    )
    acceptance_criteria: str = Field(
        min_length=1,
        max_length=5000,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class PlanDraft(BaseModel):
    summary: str = Field(
        min_length=1,
        max_length=5000,
    )
    tasks: list[DraftTask] = Field(
        min_length=1,
        max_length=50,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class PlanningState(BaseModel):
    messages: list[PlanningMessage] = Field(
        default_factory=list,
    )
    info: PlanningInfo = Field(
        default_factory=PlanningInfo,
    )
    phase: PlanningPhase = PlanningPhase.CLARIFYING
    draft: PlanDraft | None = None

    model_config = ConfigDict(
        extra="forbid",
    )