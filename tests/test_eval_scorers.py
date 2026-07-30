import asyncio
from datetime import datetime, timezone
from pathlib import Path

from agent.runtime.state import (
    Action,
    AvailableTool,
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
    ToolCall,
)
from evals.models import EvalCaseResult, EvalCheckResult, EvalTarget
from evals.report import build_run_result
from evals.node_runner import load_suite, run_case
from evals.scorers import score_decision

SUITE_PATH = Path(__file__).parents[1] / "evals" / "node_cases.json"


def get_case(case_id: str):
    suite = load_suite(SUITE_PATH)
    return next(case for case in suite.cases if case.case_id == case_id)


def test_core_eval_suite_contains_unique_plan_and_review_cases():
    suite = load_suite(SUITE_PATH)

    assert suite.version == "1.6"
    assert suite.current_time_utc == datetime(
        2026,
        7,
        13,
        tzinfo=timezone.utc,
    )
    assert len(suite.cases) == 13
    assert len({case.case_id for case in suite.cases}) == 13
    assert sum(
        case.target == EvalTarget.PLAN for case in suite.cases
    ) == 7
    assert sum(
        case.target == EvalTarget.REVIEW for case in suite.cases
    ) == 6
    for case in suite.cases:
        case.build_state()


def test_plan_scorer_accepts_complete_constraint_preserving_draft():
    case = get_case("plan_complete_goal_builds_draft")
    decision = PlanDecision(
        content="计划已准备好，进入评审。",
        next_action=Action.REVIEW,
        info=PlanningInfo(
            goal="完成 FastAPI 任务管理 API",
            acceptance_criteria="核心接口和测试可运行",
            constraints=["每天最多投入 1 小时"],
        ),
        draft=PlanningDraft(
            plan=PlanningPlan(title="FastAPI 任务管理 API"),
            tasks=[
                PlanningTask(
                    title="设计接口",
                    acceptance_criteria="完成 API 契约。",
                ),
                PlanningTask(
                    title="实现接口",
                    acceptance_criteria="核心接口可运行。",
                ),
                PlanningTask(
                    title="编写测试",
                    acceptance_criteria="核心测试通过。",
                ),
            ],
        ),
    )

    checks = score_decision(case, decision)

    assert checks
    assert all(check.passed for check in checks)


def test_constraint_scorer_accepts_equivalent_word_order():
    case = get_case("plan_complete_goal_builds_draft")
    decision = PlanDecision(
        content="计划已准备好。",
        next_action=Action.REVIEW,
        info=PlanningInfo(
            goal="完成 FastAPI 任务管理 API",
            acceptance_criteria="核心接口和测试可运行",
            constraints=["每天用于学习的时间不超过 1 小时"],
        ),
        draft=PlanningDraft(
            plan=PlanningPlan(title="FastAPI 任务管理 API"),
            tasks=[
                PlanningTask(
                    title=f"任务 {index}",
                    acceptance_criteria=f"完成任务 {index} 的验证。",
                )
                for index in range(3)
            ],
        ),
    )

    checks = score_decision(case, decision)
    constraint_check = next(
        check for check in checks if check.name == "constraint_retention"
    )

    assert constraint_check.passed is True


def test_plan_scorer_reports_each_failed_hard_requirement():
    case = get_case("plan_complete_goal_builds_draft")
    decision = PlanDecision(
        content="你还需要什么？",
        next_action=Action.CLARIFY,
        info=PlanningInfo(constraints=[]),
        draft=PlanningDraft(),
    )

    checks = score_decision(case, decision)
    failed_names = {check.name for check in checks if not check.passed}

    assert "action_correctness" in failed_names
    assert "plan_presence" in failed_names
    assert "minimum_task_count" in failed_names
    assert "acceptance_criteria_coverage" in failed_names
    assert "constraint_retention" in failed_names


def test_maximum_task_count_is_an_observable_soft_metric():
    case = get_case("plan_complete_goal_builds_draft")
    decision = PlanDecision(
        content="计划已准备好。",
        next_action=Action.REVIEW,
        info=PlanningInfo(
            goal="完成 FastAPI 任务管理 API",
            acceptance_criteria="核心接口和测试可运行",
            constraints=["每天最多投入 1 小时"],
        ),
        draft=PlanningDraft(
            plan=PlanningPlan(title="FastAPI 任务管理 API"),
            tasks=[
                PlanningTask(
                    title=f"任务 {index}",
                    acceptance_criteria=f"完成任务 {index} 的验证。",
                )
                for index in range(21)
            ],
        ),
    )

    checks = score_decision(case, decision)
    maximum_check = next(
        check for check in checks if check.name == "maximum_task_count"
    )

    assert maximum_check.passed is False
    assert maximum_check.hard is False


def test_acceptance_coverage_only_counts_leaf_tasks():
    case = get_case("plan_complete_goal_builds_draft")
    decision = PlanDecision(
        content="计划已准备好。",
        next_action=Action.REVIEW,
        info=PlanningInfo(
            goal="完成 FastAPI 任务管理 API",
            acceptance_criteria="核心接口和测试可运行",
            constraints=["每天最多投入 1 小时"],
        ),
        draft=PlanningDraft(
            plan=PlanningPlan(title="FastAPI 任务管理 API"),
            tasks=[
                PlanningTask(
                    title="分组任务",
                    subtasks=[
                        PlanningTask(
                            title=f"叶子任务 {index}",
                            acceptance_criteria=f"验收标准 {index}",
                        )
                        for index in range(2)
                    ],
                )
            ],
        ),
    )

    checks = score_decision(case, decision)
    coverage = next(
        check
        for check in checks
        if check.name == "acceptance_criteria_coverage"
    )

    assert coverage.passed is True
    assert coverage.detail == "actual=1.000; minimum=0.600"


def test_review_scorer_accepts_alternative_finding_category():
    case = get_case("review_detects_infeasible_schedule")
    decision = ReviewDecision(
        content="当前工作量无法在两天内完成。",
        next_action=Action.REPLAN,
        report=ReviewReport(
            summary="计划不可行",
            findings=[
                ReviewFinding(
                    category=ReviewCategory.FEASIBILITY,
                    severity=ReviewSeverity.WARNING,
                    description="三个多日任务无法压缩到两天。",
                )
            ],
        ),
    )

    checks = score_decision(case, decision)

    assert all(check.passed for check in checks)


def test_review_scorer_enforces_minimum_finding_severity():
    case = get_case("review_detects_missing_acceptance_criteria")
    decision = ReviewDecision(
        content="验收标准可以进一步完善。",
        next_action=Action.REPLAN,
        report=ReviewReport(
            summary="存在轻微问题",
            findings=[
                ReviewFinding(
                    category=ReviewCategory.COMPLETENESS,
                    severity=ReviewSeverity.INFO,
                    description="任务没有验收标准。",
                )
            ],
        ),
    )

    checks = score_decision(case, decision)
    finding_check = next(
        check for check in checks if check.name == "review_finding_1"
    )

    assert finding_check.passed is False


class FakeProvider:
    def __init__(self, decision):
        self.decision = decision

    async def complete(self, request, response_model):
        return self.decision


def test_runner_uses_production_node_tool_validation():
    case = get_case("plan_requests_duplicate_lookup")
    case = case.model_copy(
        update={
            "input": case.input.model_copy(
                update={
                    "available_tools": [
                        AvailableTool.LIST_USER_PLANS
                    ]
                }
            )
        }
    )
    decision = PlanDecision(
        content="查询项目详情。",
        next_action=Action.USE_TOOL,
        tool_calls=[
            ToolCall(
                tool_name=AvailableTool.GET_PLAN_TASK_TREE,
                parameter={"plan_id": 1},
            )
        ],
    )

    result = asyncio.run(run_case(case, FakeProvider(decision)))

    assert result.passed is False
    assert result.decision is None
    assert len(result.checks) == 1
    assert result.checks[0].name == "structured_output"
    assert result.checks[0].passed is False
    assert result.checks[0].detail == "AgentResponseFormatError"


def test_question_count_is_observable_but_does_not_fail_case():
    case = get_case("plan_ambiguous_goal_clarifies")
    decision = PlanDecision(
        content="你学习 Python 的主要目的是什么？例如工作还是兴趣？",
        next_action=Action.CLARIFY,
        info=PlanningInfo(goal="学习 Python"),
    )

    result = asyncio.run(run_case(case, FakeProvider(decision)))
    question_check = next(
        check for check in result.checks if check.name == "question_count"
    )

    assert question_check.passed is False
    assert question_check.hard is False
    assert result.passed is True


def test_review_quality_cases_include_completed_plan_lookup():
    case = get_case("review_detects_missing_acceptance_criteria")
    state = case.build_state()

    assert len(state.tool_results) == 1
    assert state.tool_results[0].tool_name == (
        AvailableTool.LIST_USER_PLANS
    )
    assert state.tool_results[0].output == []


def test_report_distinguishes_soft_metrics_and_adds_latency_percentiles():
    suite = load_suite(SUITE_PATH)
    case = suite.cases[0]
    latencies = [100.0, 200.0, 300.0, 400.0]
    results = [
        EvalCaseResult(
            case_id=case.case_id,
            target=case.target,
            repetition=index,
            passed=True,
            latency_ms=latency,
            checks=[
                EvalCheckResult(
                    name="question_count",
                    passed=False,
                    hard=False,
                )
            ],
        )
        for index, latency in enumerate(latencies, start=1)
    ]

    run_result = build_run_result(
        suite.model_copy(update={"cases": [case]}),
        "fake-model",
        datetime.now(timezone.utc),
        results,
    )

    assert run_result.summary.pass_rate == 1.0
    assert run_result.summary.passed_executions == 4
    assert run_result.summary.total_executions == 4
    assert run_result.summary.unique_cases == 1
    assert run_result.summary.p50_latency_ms == 250.0
    assert run_result.summary.p95_latency_ms == 385.0
    assert run_result.summary.metrics["question_count"].hard is False
    stability = run_result.summary.case_stability[case.case_id]
    assert stability.passed_executions == 4
    assert stability.total_executions == 4
    serialized = run_result.model_dump_json()
    assert serialized.index('"summary"') < serialized.index('"results"')
    assert run_result.model_dump(mode="json")["started_at"].endswith("Z")
    assert run_result.current_time_utc == suite.current_time_utc
    assert stability.pass_rate == 1.0


def test_memory_eval_separates_application_from_feasibility_conflict():
    application_case = get_case("plan_applies_long_term_constraints")
    conflict_case = get_case(
        "plan_clarifies_infeasible_memory_conflict"
    )

    assert application_case.expected.allowed_actions == [Action.REVIEW]
    assert conflict_case.expected.allowed_actions == [Action.CLARIFY]
    assert conflict_case.expected.min_question_count is None
    assert application_case.expected.required_constraints == (
        conflict_case.expected.required_constraints
    )
