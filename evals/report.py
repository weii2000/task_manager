from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from evals.models import (
    EvalCaseStability,
    EvalCaseResult,
    EvalCheckResult,
    EvalMetricSummary,
    EvalRunResult,
    EvalRunSummary,
    EvalSuite,
)


def build_run_result(
    suite: EvalSuite,
    model: str,
    started_at: datetime,
    results: list[EvalCaseResult],
) -> EvalRunResult:
    total_executions = len(results)
    passed_executions = sum(result.passed for result in results)
    metric_checks: dict[str, list[EvalCheckResult]] = defaultdict(list)
    for result in results:
        for check in result.checks:
            metric_checks[check.name].append(check)

    metrics: dict[str, EvalMetricSummary] = {}
    for name, checks in sorted(metric_checks.items()):
        hardness = {check.hard for check in checks}
        if len(hardness) != 1:
            raise ValueError(
                f"metric {name!r} mixes hard and soft checks"
            )
        passed = sum(check.passed for check in checks)
        metrics[name] = EvalMetricSummary(
            passed=passed,
            total=len(checks),
            rate=passed / len(checks),
            hard=checks[0].hard,
        )

    latencies = [result.latency_ms for result in results]
    results_by_case: dict[str, list[EvalCaseResult]] = defaultdict(list)
    for result in results:
        results_by_case[result.case_id].append(result)
    case_stability = {
        case_id: EvalCaseStability(
            passed_executions=sum(result.passed for result in case_results),
            total_executions=len(case_results),
            pass_rate=(
                sum(result.passed for result in case_results)
                / len(case_results)
            ),
        )
        for case_id, case_results in sorted(results_by_case.items())
    }
    summary = EvalRunSummary(
        passed_executions=passed_executions,
        total_executions=total_executions,
        unique_cases=len(results_by_case),
        pass_rate=(
            passed_executions / total_executions
            if total_executions
            else 0.0
        ),
        average_latency_ms=(
            sum(latencies) / total_executions
            if total_executions
            else 0.0
        ),
        p50_latency_ms=median(latencies) if latencies else 0.0,
        p95_latency_ms=_percentile(latencies, 0.95),
        case_stability=case_stability,
        metrics=metrics,
    )
    return EvalRunResult(
        suite_name=suite.name,
        suite_version=suite.version,
        model=model,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        results=results,
        summary=summary,
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return (
        ordered[lower_index]
        + (ordered[upper_index] - ordered[lower_index]) * fraction
    )


def write_run_result(
    run_result: EvalRunResult,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = run_result.started_at.strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{timestamp}.json"
    output_path.write_text(
        run_result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path


def print_run_result(
    run_result: EvalRunResult,
    output_path: Path,
) -> None:
    summary = run_result.summary
    print(
        f"Suite: {run_result.suite_name} v{run_result.suite_version}"
    )
    print(f"Model: {run_result.model}")
    print(
        "Executions: "
        f"{summary.passed_executions}/{summary.total_executions} passed "
        f"({summary.pass_rate:.1%})"
    )
    print(f"Unique cases: {summary.unique_cases}")
    print(
        f"Latency: avg={summary.average_latency_ms:.0f} ms, "
        f"p50={summary.p50_latency_ms:.0f} ms, "
        f"p95={summary.p95_latency_ms:.0f} ms"
    )
    print("Metrics:")
    for name, metric in summary.metrics.items():
        kind = "hard" if metric.hard else "soft"
        print(
            f"  {name} ({kind}): {metric.passed}/{metric.total} "
            f"({metric.rate:.1%})"
        )

    if summary.total_executions > summary.unique_cases:
        print("Case stability:")
        for case_id, stability in summary.case_stability.items():
            print(
                f"  {case_id}: {stability.passed_executions}/"
                f"{stability.total_executions} "
                f"({stability.pass_rate:.1%})"
            )

    failed_results = [
        result for result in run_result.results if not result.passed
    ]
    if failed_results:
        print("Failed cases:")
        for result in failed_results:
            failed_checks = [
                check.name
                for check in result.checks
                if not check.passed and check.hard
            ]
            reason = result.error or ", ".join(failed_checks)
            print(
                f"  {result.case_id}#{result.repetition}: {reason}"
            )
    print(f"Result: {output_path}")
