import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from agent.runtime.state import (
    Action,
    AvailableTool,
    Message,
    MessageRole,
    PlanDecision,
    PlanningDraft,
    PlanningInfo,
    PlanningPlan,
    PlanningTask,
    ReviewCategory,
    ReviewDecision,
    ReviewFinding,
    ReviewReport,
    ReviewSeverity,
    State,
    ToolCall,
)
from agent.tools.registry import TOOL_REGISTRY
from evals.workflow_runner import (
    _task_count_and_coverage,
    _write_and_print_results,
    load_suite,
    run_case,
)

SUITE_PATH = (
    Path(__file__).parents[1] / "evals" / "workflow_cases.json"
)


class SequenceProvider:
    def __init__(self, responses):
        self.responses = iter(responses)

    async def complete(self, request, response_model):
        response = next(self.responses)
        assert isinstance(response, response_model)
        return response


def make_draft(*, complete: bool = True) -> PlanningDraft:
    return PlanningDraft(
        plan=PlanningPlan(title="FastAPI 项目"),
        tasks=[
            PlanningTask(
                title=f"任务 {index}",
                acceptance_criteria=(
                    f"任务 {index} 可验证" if complete else None
                ),
            )
            for index in range(1, 4)
        ],
    )


def plan_decision(
    action: Action,
    *,
    tool_calls: list[ToolCall] | None = None,
    complete: bool = True,
) -> PlanDecision:
    return PlanDecision(
        content="规划完成" if action != Action.CLARIFY else "目标是什么？",
        next_action=action,
        tool_calls=tool_calls or [],
        info=PlanningInfo(goal="完成 FastAPI 项目"),
        draft=(
            make_draft(complete=complete)
            if action == Action.REVIEW
            else PlanningDraft()
        ),
    )


def review_decision(
    action: Action,
    *,
    blocking: bool = False,
    tool_calls: list[ToolCall] | None = None,
) -> ReviewDecision:
    findings = (
        [
            ReviewFinding(
                category=ReviewCategory.COMPLETENESS,
                severity=ReviewSeverity.BLOCKING,
                description="任务缺少验收标准",
            )
        ]
        if blocking
        else []
    )
    return ReviewDecision(
        content="评审完成",
        next_action=action,
        tool_calls=tool_calls or [],
        report=ReviewReport(summary="评审完成", findings=findings),
    )


def get_case(case_id: str):
    suite = load_suite(SUITE_PATH)
    return next(case for case in suite.cases if case.case_id == case_id)


def test_workflow_suite_has_three_distinct_paths():
    suite = load_suite(SUITE_PATH)

    assert suite.version == "1.4"
    assert suite.current_time_utc == datetime(
        2026,
        7,
        26,
        20,
        tzinfo=timezone.utc,
    )
    assert len(suite.cases) == 3
    assert len({case.case_id for case in suite.cases}) == 3


def test_clarify_workflow_resumes_with_user_follow_up():
    case = get_case("clarify_then_plan_and_confirm")
    provider = SequenceProvider(
        [
            plan_decision(Action.CLARIFY),
            plan_decision(Action.REVIEW),
            review_decision(
                Action.USE_TOOL,
                tool_calls=[
                    ToolCall(
                        tool_name=AvailableTool.LIST_USER_PLANS,
                        parameter={},
                    )
                ],
            ),
            review_decision(Action.CONFIRM),
        ]
    )

    result = asyncio.run(run_case(case, provider))

    assert result.passed is True
    assert result.decision_path == [
        Action.CLARIFY,
        Action.REVIEW,
        Action.USE_TOOL,
        Action.CONFIRM,
    ]
    assert result.model_calls == 4


def test_tool_workflow_uses_fixture_and_restores_registry():
    case = get_case("lookup_then_plan_and_confirm")
    original_handler = TOOL_REGISTRY[
        AvailableTool.LIST_USER_PLANS
    ].handler
    provider = SequenceProvider(
        [
            plan_decision(
                Action.USE_TOOL,
                tool_calls=[
                    ToolCall(
                        tool_name=AvailableTool.LIST_USER_PLANS,
                        parameter={},
                    )
                ],
            ),
            plan_decision(Action.REVIEW),
            review_decision(Action.CONFIRM),
        ]
    )

    result = asyncio.run(run_case(case, provider))

    assert result.passed is True
    assert result.tool_call_counts == {
        AvailableTool.LIST_USER_PLANS: 1
    }
    assert (
        TOOL_REGISTRY[AvailableTool.LIST_USER_PLANS].handler
        is original_handler
    )


def test_review_workflow_replans_before_confirming():
    case = get_case("blocking_review_replans_then_confirms")
    assert case.expected.decision_path is None
    provider = SequenceProvider(
        [
            review_decision(
                Action.USE_TOOL,
                tool_calls=[
                    ToolCall(
                        tool_name=AvailableTool.LIST_USER_PLANS,
                        parameter={},
                    )
                ],
            ),
            review_decision(Action.REPLAN, blocking=True),
            plan_decision(Action.REVIEW),
            review_decision(Action.CONFIRM),
        ]
    )

    result = asyncio.run(run_case(case, provider))

    assert result.passed is True
    assert result.decision_path == [
        Action.REVIEW,
        Action.USE_TOOL,
        Action.REPLAN,
        Action.REVIEW,
        Action.CONFIRM,
    ]
    assert all(
        check.name != "decision_path" for check in result.checks
    )
    assert result.state is not None
    assert result.state["revision_count"] == 1


def test_extra_valid_replan_only_fails_soft_path_checks():
    case = get_case("lookup_then_plan_and_confirm")
    provider = SequenceProvider(
        [
            plan_decision(
                Action.USE_TOOL,
                tool_calls=[
                    ToolCall(
                        tool_name=AvailableTool.LIST_USER_PLANS,
                        parameter={},
                    )
                ],
            ),
            plan_decision(Action.REVIEW),
            review_decision(Action.REPLAN, blocking=True),
            plan_decision(Action.REVIEW),
            review_decision(Action.CONFIRM),
        ]
    )

    result = asyncio.run(run_case(case, provider))

    assert result.passed is True
    failed_checks = {
        check.name: check
        for check in result.checks
        if not check.passed
    }
    assert failed_checks["decision_path"].hard is False
    assert failed_checks["model_call_budget"].hard is False


def test_workflow_rejects_dates_invented_without_user_input():
    case = get_case("lookup_then_plan_and_confirm")
    draft = make_draft()
    assert draft.plan is not None
    draft.plan.start_time = datetime(
        2025,
        8,
        1,
        tzinfo=timezone.utc,
    )
    provider = SequenceProvider(
        [
            plan_decision(
                Action.USE_TOOL,
                tool_calls=[
                    ToolCall(
                        tool_name=AvailableTool.LIST_USER_PLANS,
                        parameter={},
                    )
                ],
            ),
            PlanDecision(
                content="规划完成",
                next_action=Action.REVIEW,
                info=PlanningInfo(goal="完成求职准备"),
                draft=draft,
            ),
            review_decision(Action.CONFIRM),
        ]
    )

    result = asyncio.run(run_case(case, provider))

    invented_dates = next(
        check
        for check in result.checks
        if check.name == "no_invented_dates"
    )
    assert invented_dates.passed is False
    assert invented_dates.hard is True
    assert result.passed is False


def test_workflow_acceptance_coverage_only_counts_leaf_tasks():
    state = State(
        messages=[
            Message(role=MessageRole.USER, content="规划 FastAPI 项目")
        ],
        draft=PlanningDraft(
            plan=PlanningPlan(title="FastAPI 项目"),
            tasks=[
                PlanningTask(
                    title="分组任务",
                    subtasks=[
                        PlanningTask(
                            title="叶子任务",
                            acceptance_criteria="结果可以验证",
                        )
                    ],
                )
            ],
        ),
    )

    assert _task_count_and_coverage(state) == (2, 1.0)


def test_workflow_report_matches_node_layout_and_utc_format(tmp_path):
    suite = load_suite(SUITE_PATH)
    case = get_case("clarify_then_plan_and_confirm")
    result = asyncio.run(
        run_case(
            case,
            SequenceProvider(
                [
                    plan_decision(Action.CLARIFY),
                    plan_decision(Action.REVIEW),
                    review_decision(
                        Action.USE_TOOL,
                        tool_calls=[
                            ToolCall(
                                tool_name=(
                                    AvailableTool.LIST_USER_PLANS
                                ),
                                parameter={},
                            )
                        ],
                    ),
                    review_decision(Action.CONFIRM),
                ]
            ),
        )
    )

    _write_and_print_results(
        suite.model_copy(update={"cases": [case]}),
        "fake-model",
        datetime(2026, 7, 26, 10, tzinfo=timezone.utc),
        [result],
        tmp_path,
    )

    report_text = next(tmp_path.glob("*.json")).read_text()
    report = json.loads(report_text)
    assert list(report) == [
        "suite_name",
        "suite_version",
        "model",
        "current_time_utc",
        "started_at",
        "completed_at",
        "summary",
        "results",
    ]
    assert report["current_time_utc"] == "2026-07-26T20:00:00Z"
    assert report["started_at"].endswith("Z")
    assert "p50_latency_ms" in report["summary"]
    assert "metrics" in report["summary"]
