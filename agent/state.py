from __future__ import annotations

from datetime import datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class MessageRole(StrEnum):
    SYSTEM = auto()
    USER = auto()
    ASSISTANT = auto()


class Message(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1, max_length=5000)


class AgentPhase(StrEnum):
    PLANNING = auto()
    REVIEWING = auto()
    AWAITING_CONFIRMATION = auto()
    READY_TO_EXECUTE = auto()


class Action(StrEnum):
    PLAN = auto()
    REVIEW = auto()
    USE_TOOL = auto()
    CLARIFY = auto()
    REPLAN = auto()
    CONFIRM = auto()
    PAUSE = auto()
    READY_TO_EXECUTE = auto()


class AvailableTool(StrEnum):
    LIST_USER_PROJECTS = auto()
    GET_PROJECT_TASK_TREE = auto()


class ToolCall(BaseModel):
    call_id: str = Field(default_factory=lambda: uuid4().hex)
    tool_name: AvailableTool
    parameter: dict[str, Any]


class PlanningInfo(BaseModel):
    goal: str | None = None
    acceptance_criteria: str | None = None
    constraints: list[str] | None = None


class PlanningTask(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = None
    start_time: datetime | None = None
    due_time: datetime | None = None
    subtasks: list[PlanningTask] = Field(default_factory=list)


class PlanningDraft(BaseModel):
    tasks: list[PlanningTask] = Field(default_factory=list)


class ReviewSeverity(StrEnum):
    INFO = auto()
    WARNING = auto()
    BLOCKING = auto()


class ReviewCategory(StrEnum):
    CONFLICT = auto()
    COMPLETENESS = auto()
    FEASIBILITY = auto()
    SCHEDULE = auto()
    DUPLICATION = auto()


class ReviewFinding(BaseModel):
    category: ReviewCategory
    severity: ReviewSeverity
    description: str = Field(min_length=1, max_length=2000)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    suggestion: str | None = Field(default=None, max_length=2000)


class ReviewReport(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    findings: list[ReviewFinding] = Field(default_factory=list, max_length=20)


class BaseDecision(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    next_action: Action
    tool_calls: list[ToolCall] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_tool_calls_match_action(self) -> BaseDecision:
        if self.next_action == Action.USE_TOOL and not self.tool_calls:
            raise ValueError("use_tool action requires at least one tool call")
        if self.next_action != Action.USE_TOOL and self.tool_calls:
            raise ValueError("tool calls are only allowed for use_tool action")
        return self


class PlanDecision(BaseDecision):
    info: PlanningInfo = Field(default_factory=PlanningInfo)
    draft: PlanningDraft = Field(default_factory=PlanningDraft)

    @model_validator(mode="after")
    def validate_plan_action(self) -> PlanDecision:
        if self.next_action not in {
            Action.CLARIFY,
            Action.USE_TOOL,
            Action.REVIEW,
        }:
            raise ValueError("unsupported plan action")
        return self


class ReviewDecision(BaseDecision):
    report: ReviewReport

    @model_validator(mode="after")
    def validate_review_action(self) -> ReviewDecision:
        if self.next_action not in {
            Action.USE_TOOL,
            Action.REPLAN,
            Action.CONFIRM,
        }:
            raise ValueError("unsupported review action")
        if self.next_action == Action.REPLAN and not self.report.findings:
            raise ValueError("replan action requires at least one finding")
        if self.next_action == Action.CONFIRM and any(
            finding.severity == ReviewSeverity.BLOCKING
            for finding in self.report.findings
        ):
            raise ValueError("confirm action cannot contain blocking findings")
        return self


class HumanDecision(BaseModel):
    approved: bool
    feedback: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_rejection_feedback(self) -> HumanDecision:
        if not self.approved and not (self.feedback or "").strip():
            raise ValueError("rejection requires feedback")
        return self


class ToolResultStatus(StrEnum):
    SUCCESS = auto()
    ERROR = auto()


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ToolResult(BaseModel):
    call_id: str
    tool_name: AvailableTool
    arguments: dict[str, Any]
    phase: AgentPhase
    status: ToolResultStatus
    output: Any | None = None
    error: ToolError | None = None


class State(BaseModel):
    messages: list[Message]
    phase: AgentPhase = AgentPhase.PLANNING
    available_tools: list[AvailableTool] = Field(
        default_factory=lambda: list(AvailableTool)
    )
    info: PlanningInfo = Field(default_factory=PlanningInfo)
    draft: PlanningDraft = Field(default_factory=PlanningDraft)
    review: ReviewReport | None = None
    human_decision: HumanDecision | None = None
    next_action: Action = Action.PLAN
    pending_tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    revision_count: int = Field(default=0, ge=0)
