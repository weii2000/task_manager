from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from sqlalchemy.ext.asyncio import AsyncSession

from agent.prompt import PlanPromptBuilder, ReviewPromptBuilder
from agent.provider import LLMProvider, LLMRequest, ResponseT
from agent.runtime.context import AgentRunContext, RetrievedMemory
from agent.runtime.flow import (
    PLAN_ALLOWED_TOOLS,
    REVIEW_ALLOWED_TOOLS,
    Flow,
)
from agent.runtime.state import (
    Action,
    AgentPhase,
    AvailableTool,
    BaseDecision,
    ExecutionResult,
    Message,
    MessageRole,
    PlanDecision,
    PlanningTask,
    State,
)
from agent.tools.registry import TOOL_REGISTRY
from core.datetime_utils import to_utc_aware
from evals.models import EvalCheckResult, EvalRunSummary
from evals.report import build_run_summary

DEFAULT_SUITE_PATH = Path(__file__).with_name("workflow_cases.json")
DEFAULT_OUTPUT_DIR = Path("eval-results/workflow")


class WorkflowExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_path: list[Action] | None = Field(
        default=None,
        min_length=1,
    )
    required_actions: list[Action] = Field(default_factory=list)
    final_phase: AgentPhase = AgentPhase.CONFIRMING
    tool_call_counts: dict[AvailableTool, int] = Field(
        default_factory=dict
    )
    min_revision_count: int | None = Field(default=None, ge=0)
    min_task_count: int = Field(default=1, ge=0)
    min_acceptance_criteria_coverage: float = Field(
        default=0,
        ge=0,
        le=1,
    )
    forbid_invented_dates: bool = False
    max_model_calls: int | None = Field(default=None, ge=1)


class WorkflowCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field(min_length=1, max_length=500)
    messages: list[Message] = Field(min_length=1)
    follow_up_messages: list[str] = Field(default_factory=list)
    long_term_memories: list[RetrievedMemory] = Field(
        default_factory=list
    )
    tool_outputs: dict[AvailableTool, Any] = Field(default_factory=dict)
    first_plan_decision: PlanDecision | None = None
    expected: WorkflowExpectation


class WorkflowSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^\d+\.\d+(?:\.\d+)?$")
    current_time_utc: datetime
    cases: list[WorkflowCase] = Field(min_length=1)

    @field_validator("current_time_utc")
    @classmethod
    def normalize_current_time(cls, value: datetime) -> datetime:
        return to_utc_aware(value)

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> WorkflowSuite:
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("workflow case ids must be unique")
        return self


class WorkflowCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    repetition: int = Field(ge=1)
    passed: bool
    latency_ms: float = Field(ge=0)
    checks: list[EvalCheckResult]
    decision_path: list[Action] = Field(default_factory=list)
    final_phase: AgentPhase | None = None
    model_calls: int = Field(default=0, ge=0)
    tool_call_counts: dict[AvailableTool, int] = Field(
        default_factory=dict
    )
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    state: dict[str, Any] | None = None
    error: str | None = None


class WorkflowRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_name: str
    suite_version: str
    model: str
    current_time_utc: datetime
    started_at: datetime
    completed_at: datetime
    summary: EvalRunSummary
    results: list[WorkflowCaseResult]


class RecordingProvider:
    def __init__(
        self,
        provider: LLMProvider,
        first_plan_decision: PlanDecision | None,
    ) -> None:
        self._provider = provider
        self._first_plan_decision = first_plan_decision
        self.decisions: list[BaseDecision] = []
        self.model_calls = 0

    async def complete(
        self,
        request: LLMRequest,
        response_model: type[ResponseT],
    ) -> ResponseT:
        if (
            self._first_plan_decision is not None
            and response_model is PlanDecision
        ):
            response = response_model.model_validate(
                self._first_plan_decision.model_dump()
            )
            self._first_plan_decision = None
        else:
            self.model_calls += 1
            response = await self._provider.complete(
                request,
                response_model,
            )
        if isinstance(response, BaseDecision):
            self.decisions.append(response)
        return response


class _EvalDB:
    def in_transaction(self) -> bool:
        return True


async def _unexpected_persist(
    state: State,
    context: AgentRunContext,
) -> ExecutionResult:
    raise RuntimeError("workflow eval must stop before execution")


def load_suite(path: Path) -> WorkflowSuite:
    return WorkflowSuite.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def _make_tool_handler(output: Any):
    async def handler(context: AgentRunContext, arguments: Any) -> Any:
        return output

    return handler


def _missing_tool_handler(tool_name: AvailableTool):
    async def handler(context: AgentRunContext, arguments: Any) -> Any:
        raise RuntimeError(
            f"workflow case has no fixture for {tool_name.value}"
        )

    return handler


@contextmanager
def _tool_fixtures(
    outputs: dict[AvailableTool, Any],
) -> Iterator[None]:
    originals = TOOL_REGISTRY.copy()
    # ponytail: runner is sequential; inject registries before parallelizing.
    try:
        for tool_name, definition in originals.items():
            handler = (
                _make_tool_handler(outputs[tool_name])
                if tool_name in outputs
                else _missing_tool_handler(tool_name)
            )
            TOOL_REGISTRY[tool_name] = replace(
                definition,
                handler=handler,
            )
        yield
    finally:
        TOOL_REGISTRY.clear()
        TOOL_REGISTRY.update(originals)


def _flatten_tasks(state: State) -> list[PlanningTask]:
    tasks = list(state.draft.tasks)
    flattened = []
    while tasks:
        task = tasks.pop()
        flattened.append(task)
        tasks.extend(task.subtasks)
    return flattened


def _task_count_and_coverage(state: State) -> tuple[int, float]:
    flattened = _flatten_tasks(state)
    leaf_tasks = [task for task in flattened if not task.subtasks]
    covered = sum(
        bool((task.acceptance_criteria or "").strip())
        for task in leaf_tasks
    )
    coverage = covered / len(leaf_tasks) if leaf_tasks else 0
    return len(flattened), coverage


def score_workflow(
    case: WorkflowCase,
    state: State,
    provider: RecordingProvider,
) -> list[EvalCheckResult]:
    expected = case.expected
    decision_path = [
        decision.next_action for decision in provider.decisions
    ]
    tool_call_counts = Counter(
        call.tool_name
        for decision in provider.decisions
        for call in decision.tool_calls
    )
    missing_actions = [
        action
        for action in expected.required_actions
        if action not in decision_path
    ]
    task_count, coverage = _task_count_and_coverage(state)
    checks = [
        EvalCheckResult(
            name="final_phase",
            passed=state.phase == expected.final_phase,
            detail=f"actual={state.phase.value}",
        ),
        EvalCheckResult(
            name="required_actions",
            passed=not missing_actions,
            detail=f"missing={[action.value for action in missing_actions]}",
        ),
    ]
    if expected.decision_path is not None:
        checks.append(
            EvalCheckResult(
                name="decision_path",
                passed=decision_path == expected.decision_path,
                hard=False,
                detail=" -> ".join(
                    action.value for action in decision_path
                ),
            )
        )
    checks.extend(
        [
            EvalCheckResult(
                name="tool_call_counts",
                passed=(
                    dict(tool_call_counts)
                    == expected.tool_call_counts
                ),
                hard=False,
                detail=json.dumps(
                    {
                        tool.value: count
                        for tool, count in tool_call_counts.items()
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
            EvalCheckResult(
                name="minimum_task_count",
                passed=task_count >= expected.min_task_count,
                detail=f"actual={task_count}",
            ),
            EvalCheckResult(
                name="acceptance_criteria_coverage",
                passed=(
                    coverage
                    >= expected.min_acceptance_criteria_coverage
                ),
                detail=f"actual={coverage:.1%}",
            ),
        ]
    )
    if expected.min_revision_count is not None:
        checks.append(
            EvalCheckResult(
                name="minimum_revision_count",
                passed=(
                    state.revision_count
                    >= expected.min_revision_count
                ),
                detail=f"actual={state.revision_count}",
            )
        )
    if expected.forbid_invented_dates:
        plan = state.draft.plan
        dated_tasks = [
            task.title
            for task in _flatten_tasks(state)
            if task.start_time is not None or task.due_time is not None
        ]
        plan_has_dates = plan is not None and (
            plan.start_time is not None or plan.due_time is not None
        )
        checks.append(
            EvalCheckResult(
                name="no_invented_dates",
                passed=not plan_has_dates and not dated_tasks,
                detail=(
                    f"plan_has_dates={plan_has_dates}; "
                    f"dated_tasks={dated_tasks}"
                ),
            )
        )
    if expected.max_model_calls is not None:
        checks.append(
            EvalCheckResult(
                name="model_call_budget",
                passed=provider.model_calls <= expected.max_model_calls,
                hard=False,
                detail=f"actual={provider.model_calls}",
            )
        )
    return checks


async def run_case(
    case: WorkflowCase,
    provider: LLMProvider,
    repetition: int = 1,
    current_time_utc: datetime | None = None,
) -> WorkflowCaseResult:
    state = State(messages=case.messages)
    recording_provider = RecordingProvider(
        provider,
        case.first_plan_decision,
    )
    flow = Flow(
        provider=recording_provider,
        persist_plan=_unexpected_persist,
        plan_prompt_builder=PlanPromptBuilder(
            PLAN_ALLOWED_TOOLS,
            current_time_utc=current_time_utc,
        ),
        review_prompt_builder=ReviewPromptBuilder(
            REVIEW_ALLOWED_TOOLS,
            current_time_utc=current_time_utc,
        ),
    )
    context = AgentRunContext(
        user_id=1,
        db=cast(AsyncSession, _EvalDB()),
        retrieved_memories=tuple(case.long_term_memories),
    )
    follow_ups = iter(case.follow_up_messages)
    started = perf_counter()
    try:
        with _tool_fixtures(case.tool_outputs):
            while True:
                state, _ = await flow.run(state, context)
                if state.phase == AgentPhase.CONFIRMING:
                    break
                follow_up = next(follow_ups, None)
                if (
                    state.phase != AgentPhase.PLANNING
                    or state.next_action is not None
                    or follow_up is None
                ):
                    break
                state.messages.append(
                    Message(
                        role=MessageRole.USER,
                        content=follow_up,
                    )
                )
                state.next_action = Action.PLAN

        checks = score_workflow(case, state, recording_provider)
        return WorkflowCaseResult(
            case_id=case.case_id,
            repetition=repetition,
            passed=all(
                check.passed or not check.hard for check in checks
            ),
            latency_ms=(perf_counter() - started) * 1000,
            checks=checks,
            decision_path=[
                decision.next_action
                for decision in recording_provider.decisions
            ],
            final_phase=state.phase,
            model_calls=recording_provider.model_calls,
            tool_call_counts=dict(
                Counter(
                    call.tool_name
                    for decision in recording_provider.decisions
                    for call in decision.tool_calls
                )
            ),
            decisions=[
                decision.model_dump(mode="json")
                for decision in recording_provider.decisions
            ],
            state=state.model_dump(mode="json"),
        )
    except Exception as exc:
        return WorkflowCaseResult(
            case_id=case.case_id,
            repetition=repetition,
            passed=False,
            latency_ms=(perf_counter() - started) * 1000,
            checks=[
                EvalCheckResult(
                    name="workflow_execution",
                    passed=False,
                    detail=type(exc).__name__,
                )
            ],
            decision_path=[
                decision.next_action
                for decision in recording_provider.decisions
            ],
            model_calls=recording_provider.model_calls,
            decisions=[
                decision.model_dump(mode="json")
                for decision in recording_provider.decisions
            ],
            error=f"{type(exc).__name__}: {exc}",
        )


async def run_suite(
    suite: WorkflowSuite,
    provider: LLMProvider,
    repetitions: int,
) -> list[WorkflowCaseResult]:
    return [
        await run_case(
            case,
            provider,
            repetition,
            suite.current_time_utc,
        )
        for repetition in range(1, repetitions + 1)
        for case in suite.cases
    ]


def _filter_suite(
    suite: WorkflowSuite,
    case_ids: list[str] | None,
) -> WorkflowSuite:
    if not case_ids:
        return suite
    selected = set(case_ids)
    cases = [case for case in suite.cases if case.case_id in selected]
    missing = selected - {case.case_id for case in cases}
    if missing:
        raise ValueError(f"unknown workflow case ids: {sorted(missing)}")
    return suite.model_copy(update={"cases": cases})


def _write_and_print_results(
    suite: WorkflowSuite,
    model: str,
    started_at: datetime,
    results: list[WorkflowCaseResult],
    output_dir: Path,
) -> float:
    run_result = WorkflowRunResult(
        suite_name=suite.name,
        suite_version=suite.version,
        model=model,
        current_time_utc=suite.current_time_utc,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        summary=build_run_summary(results),
        results=results,
    )
    summary = run_result.summary
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{timestamp}.json"
    output_path.write_text(
        run_result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(f"Suite: {suite.name} v{suite.version}")
    print(f"Model: {model}")
    print(
        f"Executions: {summary.passed_executions}/"
        f"{summary.total_executions} passed "
        f"({summary.pass_rate:.1%})"
    )
    print(
        f"Latency: avg={summary.average_latency_ms:.0f} ms, "
        f"p50={summary.p50_latency_ms:.0f} ms, "
        f"p95={summary.p95_latency_ms:.0f} ms"
    )
    for result in results:
        path = " -> ".join(action.value for action in result.decision_path)
        status = "PASS" if result.passed else "FAIL"
        detail = result.error or path
        print(f"  {status} {result.case_id}: {detail}")
    print(f"Result: {output_path}")
    return summary.pass_rate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full agent workflow evaluations."
    )
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE_PATH)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--fail-under", type=float, default=None)
    return parser.parse_args()


async def _run_from_args(args: argparse.Namespace) -> int:
    from core.config import settings
    from dependencies.agent import get_llm_provider

    if args.repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    if args.fail_under is not None and not 0 <= args.fail_under <= 1:
        raise ValueError("fail-under must be between 0 and 1")

    suite = _filter_suite(load_suite(args.suite), args.case_ids)
    started_at = datetime.now(timezone.utc)
    results = await run_suite(
        suite,
        get_llm_provider(),
        args.repetitions,
    )
    pass_rate = _write_and_print_results(
        suite,
        settings.OPENAI_MODEL,
        started_at,
        results,
        args.output_dir,
    )
    return int(
        args.fail_under is not None and pass_rate < args.fail_under
    )


def main() -> int:
    return asyncio.run(_run_from_args(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
