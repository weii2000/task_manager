from __future__ import annotations

import unicodedata

from agent.runtime.state import (
    BaseDecision,
    PlanDecision,
    PlanningProject,
    PlanningTask,
    ReviewDecision,
    ReviewSeverity,
)
from evals.models import EvalCase, EvalCheckResult

SEVERITY_RANK = {
    ReviewSeverity.INFO: 0,
    ReviewSeverity.WARNING: 1,
    ReviewSeverity.BLOCKING: 2,
}


def score_decision(
    case: EvalCase,
    decision: BaseDecision,
) -> list[EvalCheckResult]:
    checks = [
        EvalCheckResult(name="structured_output", passed=True),
        EvalCheckResult(
            name="action_correctness",
            passed=decision.next_action
            in case.expected.allowed_actions,
            detail=(
                f"actual={decision.next_action.value}; "
                f"allowed={[
                    action.value
                    for action in case.expected.allowed_actions
                ]}"
            ),
        ),
    ]
    checks.extend(_score_tool(case, decision))
    checks.extend(_score_content(case, decision))

    if isinstance(decision, PlanDecision):
        checks.extend(_score_plan(case, decision))
    elif isinstance(decision, ReviewDecision):
        checks.extend(_score_review(case, decision))

    return checks


def _score_tool(
    case: EvalCase,
    decision: BaseDecision,
) -> list[EvalCheckResult]:
    required_tool = case.expected.required_tool
    if required_tool is None:
        return []

    actual_tools = [call.tool_name for call in decision.tool_calls]
    return [
        EvalCheckResult(
            name="tool_selection",
            passed=required_tool in actual_tools,
            detail=(
                f"required={required_tool.value}; "
                f"actual={[tool.value for tool in actual_tools]}"
            ),
        )
    ]


def _score_content(
    case: EvalCase,
    decision: BaseDecision,
) -> list[EvalCheckResult]:
    checks: list[EvalCheckResult] = []
    expected = case.expected

    if (
        expected.min_question_count is not None
        or expected.max_question_count is not None
    ):
        question_count = decision.content.count("?") + decision.content.count(
            "？"
        )
        meets_minimum = (
            expected.min_question_count is None
            or question_count >= expected.min_question_count
        )
        meets_maximum = (
            expected.max_question_count is None
            or question_count <= expected.max_question_count
        )
        checks.append(
            EvalCheckResult(
                name="question_count",
                passed=meets_minimum and meets_maximum,
                hard=False,
                detail=(
                    f"actual={question_count}; minimum="
                    f"{expected.min_question_count}; maximum="
                    f"{expected.max_question_count}"
                ),
            )
        )

    if expected.forbidden_content_terms:
        normalized_content = _normalize_text(decision.content)
        present_terms = [
            term
            for term in expected.forbidden_content_terms
            if _normalize_text(term) in normalized_content
        ]
        checks.append(
            EvalCheckResult(
                name="forbidden_content",
                passed=not present_terms,
                detail=f"present={present_terms}",
            )
        )

    return checks


def _score_plan(
    case: EvalCase,
    decision: PlanDecision,
) -> list[EvalCheckResult]:
    checks: list[EvalCheckResult] = []
    expected = case.expected
    project = decision.draft.project
    tasks = _flatten_tasks(decision.draft.tasks)

    if expected.require_project is not None:
        checks.append(
            EvalCheckResult(
                name="project_presence",
                passed=(project is not None) == expected.require_project,
                detail=f"present={project is not None}",
            )
        )

    if expected.require_project_start_time:
        checks.append(
            EvalCheckResult(
                name="project_start_time",
                passed=project is not None
                and project.start_time is not None,
                detail=(
                    "missing"
                    if project is None or project.start_time is None
                    else project.start_time.isoformat()
                ),
            )
        )

    if expected.require_project_due_time:
        checks.append(
            EvalCheckResult(
                name="project_due_time",
                passed=project is not None and project.due_time is not None,
                detail=(
                    "missing"
                    if project is None or project.due_time is None
                    else project.due_time.isoformat()
                ),
            )
        )

    if expected.min_task_count is not None:
        checks.append(
            EvalCheckResult(
                name="minimum_task_count",
                passed=len(tasks) >= expected.min_task_count,
                detail=(
                    f"actual={len(tasks)}; "
                    f"minimum={expected.min_task_count}"
                ),
            )
        )

    if expected.max_task_count is not None:
        checks.append(
            EvalCheckResult(
                name="maximum_task_count",
                passed=len(tasks) <= expected.max_task_count,
                hard=False,
                detail=(
                    f"actual={len(tasks)}; "
                    f"maximum={expected.max_task_count}"
                ),
            )
        )

    if expected.min_acceptance_criteria_coverage is not None:
        covered_count = sum(
            bool((task.acceptance_criteria or "").strip()) for task in tasks
        )
        coverage = covered_count / len(tasks) if tasks else 0.0
        checks.append(
            EvalCheckResult(
                name="acceptance_criteria_coverage",
                passed=(
                    coverage
                    >= expected.min_acceptance_criteria_coverage
                ),
                detail=(
                    f"actual={coverage:.3f}; minimum="
                    f"{expected.min_acceptance_criteria_coverage:.3f}"
                ),
            )
        )

    if expected.required_constraints:
        constraints = decision.info.constraints or []
        constraint_text = _normalize_text(" ".join(constraints))
        missing_constraints = [
            constraint
            for constraint in expected.required_constraints
            if not all(
                any(
                    _normalize_text(term) in constraint_text
                    for term in concept_group
                )
                for concept_group in constraint.concept_groups
            )
        ]
        checks.append(
            EvalCheckResult(
                name="constraint_retention",
                passed=not missing_constraints,
                detail=(
                    "missing_constraints="
                    f"{[
                        constraint.model_dump(mode='json')
                        for constraint in missing_constraints
                    ]}"
                ),
            )
        )

    if expected.tasks_within_project_window:
        checks.append(_score_project_window(project, tasks))

    return checks


def _score_review(
    case: EvalCase,
    decision: ReviewDecision,
) -> list[EvalCheckResult]:
    checks: list[EvalCheckResult] = []
    for index, expected_finding in enumerate(
        case.expected.required_findings,
        start=1,
    ):
        matching = [
            finding
            for finding in decision.report.findings
            if finding.category in expected_finding.categories
            and SEVERITY_RANK[finding.severity]
            >= SEVERITY_RANK[expected_finding.minimum_severity]
        ]
        checks.append(
            EvalCheckResult(
                name=f"review_finding_{index}",
                passed=bool(matching),
                detail=(
                    "expected_categories="
                    f"{[
                        category.value
                        for category in expected_finding.categories
                    ]}; minimum_severity="
                    f"{expected_finding.minimum_severity.value}"
                ),
            )
        )
    return checks


def _score_project_window(
    project: PlanningProject | None,
    tasks: list[PlanningTask],
) -> EvalCheckResult:
    if project is None:
        return EvalCheckResult(
            name="project_window",
            passed=False,
            detail="project is missing",
        )

    violations: list[str] = []
    for task in tasks:
        if (
            project.start_time is not None
            and task.start_time is not None
            and task.start_time < project.start_time
        ):
            violations.append(f"{task.title}: starts before project")
        if (
            project.due_time is not None
            and task.due_time is not None
            and task.due_time > project.due_time
        ):
            violations.append(f"{task.title}: ends after project")

    return EvalCheckResult(
        name="project_window",
        passed=not violations,
        detail=f"violations={violations}",
    )


def _flatten_tasks(tasks: list[PlanningTask]) -> list[PlanningTask]:
    flattened: list[PlanningTask] = []
    for task in tasks:
        flattened.append(task)
        flattened.extend(_flatten_tasks(task.subtasks))
    return flattened


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())
