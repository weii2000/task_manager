"""Agent 运行状态与数据契约。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum, auto
from typing import Annotated, Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from core.datetime_utils import to_utc_aware
from models.enums import TaskPriority


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
    CONFIRMING = auto()
    EXECUTING = auto()
    COMPLETED = auto()


class Action(StrEnum):
    PLAN = auto()
    REVIEW = auto()
    USE_TOOL = auto()
    CLARIFY = auto()
    REPLAN = auto()
    CONFIRM = auto()
    EXECUTE = auto()


class AvailableTool(StrEnum):
    LIST_USER_PLANS = auto()
    GET_PLAN_TASK_TREE = auto()


class ToolCall(BaseModel):
    call_id: str = Field(default_factory=lambda: uuid4().hex)
    tool_name: AvailableTool
    parameter: dict[str, Any]


class PlanningInfo(BaseModel):
    goal: str | None = Field(default=None, max_length=2000)
    acceptance_criteria: str | None = Field(
        default=None,
        max_length=5000,
    )
    constraints: list[
        Annotated[str, Field(min_length=1, max_length=1000)]
    ] | None = Field(default=None, max_length=20)


class PlanningPlan(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    start_time: datetime | None = None
    due_time: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("plan title cannot be blank")
        return normalized

    @field_validator("start_time", "due_time")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        if not value:
            return value
        return to_utc_aware(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> PlanningPlan:
        if (
            self.start_time is not None
            and self.due_time is not None
            and self.due_time < self.start_time
        ):
            raise ValueError("plan due time cannot be before start time")
        return self


class PlanningTask(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    acceptance_criteria: str | None = Field(default=None, max_length=5000)
    priority: TaskPriority = TaskPriority.LOW
    start_time: datetime | None = None
    due_time: datetime | None = None
    subtasks: list[PlanningTask] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("task title cannot be blank")
        return normalized

    @field_validator("start_time", "due_time")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        if not value:
            return value
        return to_utc_aware(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> PlanningTask:
        if (
            self.start_time is not None
            and self.due_time is not None
            and self.due_time < self.start_time
        ):
            raise ValueError("task due time cannot be before start time")
        return self


class PlanningDraft(BaseModel):
    plan: PlanningPlan | None = None
    tasks: list[PlanningTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_task_tree_limits(self) -> PlanningDraft:
        task_count = 0

        def visit(tasks: list[PlanningTask], depth: int) -> None:
            nonlocal task_count
            for task in tasks:
                if depth > 3:
                    raise ValueError("task tree depth cannot exceed 3")
                task_count += 1
                if task_count > 100:
                    raise ValueError("task count cannot exceed 100")
                visit(task.subtasks, depth + 1)

        visit(self.tasks, 1)
        return self


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
        if self.next_action == Action.REVIEW:
            if self.draft.plan is None:
                raise ValueError("review action requires plan details")
            if not self.draft.tasks:
                raise ValueError("review action requires at least one task")
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


class ExecutionResult(BaseModel):
    plan_id: int = Field(gt=0)
    plan_title: str = Field(min_length=1, max_length=100)
    created_task_count: int = Field(ge=1, le=100)
    completed_at: datetime


class ToolResultStatus(StrEnum):
    SUCCESS = auto()
    ERROR = auto()


class ToolError(BaseModel):
    code: str
    message: str


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
    memory_summary: str | None = Field(
        default=None,
        max_length=5000,
    )
    summarized_message_count: int = Field(default=0, ge=0)
    phase: AgentPhase = AgentPhase.PLANNING
    available_tools: list[AvailableTool] = Field(
        default_factory=lambda: list(AvailableTool)
    )
    info: PlanningInfo = Field(default_factory=PlanningInfo)
    draft: PlanningDraft = Field(default_factory=PlanningDraft)
    review: ReviewReport | None = None
    human_decision: HumanDecision | None = None
    execution: ExecutionResult | None = None
    next_action: Action | None = Action.PLAN
    pending_tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    revision_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_phase_contract(self) -> State:
        allowed_actions: dict[AgentPhase, set[Action | None]] = {
            AgentPhase.PLANNING: {
                None,
                Action.PLAN,
                Action.CLARIFY,
                Action.USE_TOOL,
                Action.REVIEW,
            },
            AgentPhase.REVIEWING: {
                Action.REVIEW,
                Action.USE_TOOL,
                Action.REPLAN,
                Action.CONFIRM,
            },
            AgentPhase.CONFIRMING: {None},
            AgentPhase.EXECUTING: {Action.EXECUTE},
            AgentPhase.COMPLETED: {None},
        }
        if self.next_action not in allowed_actions[self.phase]:
            raise ValueError(
                "next action is incompatible with the current phase"
            )

        if self.phase == AgentPhase.COMPLETED:
            if self.execution is None:
                raise ValueError("completed phase requires execution result")
        elif self.execution is not None:
            raise ValueError(
                "execution result is only allowed in completed phase"
            )
        return self

    @model_validator(mode="after")
    def validate_memory(self) -> State:
        if self.summarized_message_count > len(self.messages):
            raise ValueError(
                "summarized message count cannot exceed message count"
            )

        if self.summarized_message_count == 0:
            if self.memory_summary is not None:
                raise ValueError(
                    "memory summary requires summarized messages"
                )
        elif self.memory_summary is None:
            raise ValueError(
                "summarized messages require memory summary"
            )

        return self
