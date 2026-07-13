from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.context import RetrievedMemory
from agent.state import (
    Action,
    AgentPhase,
    AvailableTool,
    Message,
    PlanningDraft,
    PlanningInfo,
    ReviewCategory,
    ReviewReport,
    ReviewSeverity,
    State,
    ToolResult,
)


class EvalTarget(StrEnum):
    PLAN = "plan"
    REVIEW = "review"


class EvalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[Message] = Field(min_length=1)
    info: PlanningInfo = Field(default_factory=PlanningInfo)
    draft: PlanningDraft = Field(default_factory=PlanningDraft)
    previous_review: ReviewReport | None = None
    available_tools: list[AvailableTool] = Field(
        default_factory=lambda: list(AvailableTool)
    )
    long_term_memories: list[RetrievedMemory] = Field(
        default_factory=list
    )
    tool_results: list[ToolResult] = Field(default_factory=list)
    revision_count: int = Field(default=0, ge=0)


class FindingExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[ReviewCategory] = Field(min_length=1)
    minimum_severity: ReviewSeverity = ReviewSeverity.INFO


class ConstraintExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_groups: list[list[str]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_concept_groups(self) -> ConstraintExpectation:
        if any(
            not group or any(not term.strip() for term in group)
            for group in self.concept_groups
        ):
            raise ValueError("constraint concept groups cannot be empty")
        return self


class EvalExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_actions: list[Action] = Field(min_length=1)
    required_tool: AvailableTool | None = None
    require_project: bool | None = None
    require_project_start_time: bool = False
    require_project_due_time: bool = False
    tasks_within_project_window: bool = False
    min_task_count: int | None = Field(default=None, ge=0)
    max_task_count: int | None = Field(default=None, ge=0)
    min_acceptance_criteria_coverage: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    min_question_count: int | None = Field(default=None, ge=0)
    max_question_count: int | None = Field(default=None, ge=0)
    required_constraints: list[ConstraintExpectation] = Field(
        default_factory=list
    )
    required_findings: list[FindingExpectation] = Field(
        default_factory=list
    )
    forbidden_content_terms: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_task_count_range(self) -> EvalExpectation:
        if (
            self.min_task_count is not None
            and self.max_task_count is not None
            and self.min_task_count > self.max_task_count
        ):
            raise ValueError(
                "minimum task count cannot exceed maximum task count"
            )
        if (
            self.min_question_count is not None
            and self.max_question_count is not None
            and self.min_question_count > self.max_question_count
        ):
            raise ValueError(
                "minimum question count cannot exceed maximum question count"
            )
        return self


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field(min_length=1, max_length=500)
    target: EvalTarget
    input: EvalInput
    expected: EvalExpectation

    @model_validator(mode="after")
    def validate_actions_match_target(self) -> EvalCase:
        allowed_by_target = {
            EvalTarget.PLAN: {
                Action.CLARIFY,
                Action.USE_TOOL,
                Action.REVIEW,
            },
            EvalTarget.REVIEW: {
                Action.USE_TOOL,
                Action.REPLAN,
                Action.CONFIRM,
            },
        }
        if any(
            action not in allowed_by_target[self.target]
            for action in self.expected.allowed_actions
        ):
            raise ValueError("expected action is incompatible with target")
        if (
            self.target == EvalTarget.PLAN
            and self.expected.required_findings
        ):
            raise ValueError("plan cases cannot require review findings")
        return self

    def build_state(self) -> State:
        phase = (
            AgentPhase.PLANNING
            if self.target == EvalTarget.PLAN
            else AgentPhase.REVIEWING
        )
        next_action = (
            Action.PLAN
            if self.target == EvalTarget.PLAN
            else Action.REVIEW
        )
        return State(
            messages=self.input.messages,
            phase=phase,
            available_tools=self.input.available_tools,
            info=self.input.info,
            draft=self.input.draft,
            review=self.input.previous_review,
            next_action=next_action,
            tool_results=self.input.tool_results,
            revision_count=self.input.revision_count,
        )


class EvalSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^\d+\.\d+(?:\.\d+)?$")
    cases: list[EvalCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> EvalSuite:
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("eval case ids must be unique")
        return self


class EvalCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    hard: bool = True
    detail: str | None = None


class EvalCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    target: EvalTarget
    repetition: int = Field(ge=1)
    passed: bool
    latency_ms: float = Field(ge=0)
    checks: list[EvalCheckResult]
    decision: dict[str, object] | None = None
    error: str | None = None


class EvalMetricSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: int = Field(ge=0)
    total: int = Field(ge=0)
    rate: float = Field(ge=0, le=1)
    hard: bool


class EvalCaseStability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed_executions: int = Field(ge=0)
    total_executions: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)


class EvalRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed_executions: int = Field(ge=0)
    total_executions: int = Field(ge=0)
    unique_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    p50_latency_ms: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    case_stability: dict[str, EvalCaseStability]
    metrics: dict[str, EvalMetricSummary]


class EvalRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_name: str
    suite_version: str
    model: str
    started_at: datetime
    completed_at: datetime
    results: list[EvalCaseResult]
    summary: EvalRunSummary
