from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent.prompt import PlanPromptBuilder, ReviewPromptBuilder
from agent.provider import LLMProvider, ResponseT
from agent.runtime.context import AgentRunContext
from agent.runtime.flow import PLAN_ALLOWED_TOOLS, REVIEW_ALLOWED_TOOLS
from agent.runtime.node import PlanNode, ReviewNode
from agent.runtime.state import PlanDecision, ReviewDecision
from evals.models import (
    EvalCase,
    EvalCaseResult,
    EvalCheckResult,
    EvalSuite,
    EvalTarget,
)
from evals.report import build_run_result, print_run_result, write_run_result
from evals.scorers import score_decision

DEFAULT_SUITE_PATH = Path(__file__).with_name("cases.json")
DEFAULT_OUTPUT_DIR = Path("eval-results")


class CapturingProvider:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self.response: BaseModel | None = None

    async def complete(
        self,
        request,
        response_model: type[ResponseT],
    ) -> ResponseT:
        response = await self._provider.complete(request, response_model)
        self.response = response
        return response


def load_suite(path: Path) -> EvalSuite:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EvalSuite.model_validate(payload)


async def run_case(
    case: EvalCase,
    provider: LLMProvider,
    repetition: int = 1,
) -> EvalCaseResult:
    state = case.build_state()
    capturing_provider = CapturingProvider(provider)
    context = AgentRunContext(
        user_id=1,
        db=cast(AsyncSession, None),
        retrieved_memories=tuple(case.input.long_term_memories),
    )
    started = perf_counter()
    try:
        if case.target == EvalTarget.PLAN:
            node = PlanNode(
                provider=capturing_provider,
                prompt_builder=PlanPromptBuilder(PLAN_ALLOWED_TOOLS),
                allowed_tools=PLAN_ALLOWED_TOOLS,
            )
        else:
            node = ReviewNode(
                provider=capturing_provider,
                prompt_builder=ReviewPromptBuilder(REVIEW_ALLOWED_TOOLS),
                allowed_tools=REVIEW_ALLOWED_TOOLS,
            )

        await node.exec(state, context)
        decision = capturing_provider.response
        if not isinstance(decision, (PlanDecision, ReviewDecision)):
            raise TypeError("provider returned an unexpected decision type")
        checks = score_decision(case, decision)
        return EvalCaseResult(
            case_id=case.case_id,
            target=case.target,
            repetition=repetition,
            passed=all(
                check.passed or not check.hard for check in checks
            ),
            latency_ms=(perf_counter() - started) * 1000,
            checks=checks,
            decision=decision.model_dump(mode="json"),
        )
    except Exception as exc:
        return EvalCaseResult(
            case_id=case.case_id,
            target=case.target,
            repetition=repetition,
            passed=False,
            latency_ms=(perf_counter() - started) * 1000,
            checks=[
                EvalCheckResult(
                    name="structured_output",
                    passed=False,
                    detail=type(exc).__name__,
                )
            ],
            error=f"{type(exc).__name__}: {exc}",
        )


async def run_suite(
    suite: EvalSuite,
    provider: LLMProvider,
    repetitions: int,
) -> list[EvalCaseResult]:
    results: list[EvalCaseResult] = []
    for repetition in range(1, repetitions + 1):
        for case in suite.cases:
            results.append(await run_case(case, provider, repetition))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run offline evaluations against the configured LLM."
    )
    parser.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_SUITE_PATH,
        help="Path to an eval suite JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory used for JSON results.",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="Run one case id; repeat the option to select more cases.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Number of sequential runs per case.",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit non-zero when the case pass rate is below this value.",
    )
    return parser.parse_args()


def _filter_suite(
    suite: EvalSuite,
    case_ids: list[str] | None,
) -> EvalSuite:
    if not case_ids:
        return suite
    selected = set(case_ids)
    cases = [case for case in suite.cases if case.case_id in selected]
    missing = selected - {case.case_id for case in cases}
    if missing:
        raise ValueError(f"unknown eval case ids: {sorted(missing)}")
    return suite.model_copy(update={"cases": cases})


async def _run_from_args(args: argparse.Namespace) -> int:
    from core.config import settings
    from dependencies.agent import get_llm_provider

    if args.repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    if args.fail_under is not None and not 0 <= args.fail_under <= 1:
        raise ValueError("fail-under must be between 0 and 1")

    suite = _filter_suite(load_suite(args.suite), args.case_ids)
    provider = get_llm_provider()
    started_at = datetime.now(timezone.utc)
    results = await run_suite(suite, provider, args.repetitions)
    run_result = build_run_result(
        suite,
        settings.OPENAI_MODEL,
        started_at,
        results,
    )
    output_path = write_run_result(run_result, args.output_dir)
    print_run_result(run_result, output_path)

    if (
        args.fail_under is not None
        and run_result.summary.pass_rate < args.fail_under
    ):
        return 1
    return 0


def main() -> int:
    return asyncio.run(_run_from_args(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
