import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.context import AgentRunContext
from agent.flow import Flow
from agent.state import (
    Action,
    AgentPhase,
    AvailableTool,
    ExecutionResult,
    HumanDecision,
    Message,
    MessageRole,
    PlanDecision,
    PlanningDraft,
    PlanningInfo,
    PlanningProject,
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
from exceptions.agent import (
    AgentFlowEntryPointError,
    AgentFlowStepLimitExceededError,
)


def make_state() -> State:
    return State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")]
    )


def make_context() -> AgentRunContext:
    db = MagicMock()
    db.in_transaction.return_value = True
    return AgentRunContext(user_id=1, db=db)


def make_plan_decision(
    action: Action = Action.CLARIFY,
    content: str = "你的目标是什么？",
) -> PlanDecision:
    draft = PlanningDraft()
    if action == Action.REVIEW:
        draft = PlanningDraft(
            project=PlanningProject(title="学习计划"),
            tasks=[PlanningTask(title="完成第一阶段学习")],
        )
    return PlanDecision(
        content=content,
        next_action=action,
        info=PlanningInfo(goal="完成学习计划"),
        draft=draft,
    )


def make_finding(
    severity: ReviewSeverity = ReviewSeverity.BLOCKING,
) -> ReviewFinding:
    return ReviewFinding(
        category=ReviewCategory.COMPLETENESS,
        severity=severity,
        description="计划缺少可验证的完成标准",
        suggestion="补充明确的验收条件",
    )


def make_review_decision(
    action: Action,
    *,
    findings: list[ReviewFinding] | None = None,
    tool_calls: list[ToolCall] | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        content="评审完成",
        next_action=action,
        tool_calls=tool_calls or [],
        report=ReviewReport(
            summary="计划结构清晰",
            findings=findings or [],
        ),
    )


def test_flow_stops_after_clarify():
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=make_plan_decision())
    flow = Flow(provider=provider)

    result_state, response = asyncio.run(
        flow.run(make_state(), make_context())
    )

    assert result_state.messages[-1].content == "你的目标是什么？"
    assert result_state.phase == AgentPhase.PLANNING
    assert result_state.next_action is None
    assert response == "你的目标是什么？"
    provider.complete.assert_awaited_once()


def test_plan_review_confirm_flow_pauses_for_human():
    provider = AsyncMock()
    provider.complete = AsyncMock(
        side_effect=[
            make_plan_decision(Action.REVIEW),
            make_review_decision(
                Action.CONFIRM,
                findings=[make_finding(ReviewSeverity.WARNING)],
            ),
        ]
    )
    flow = Flow(provider=provider)

    result_state, response = asyncio.run(
        flow.run(make_state(), make_context())
    )

    assert result_state.phase == AgentPhase.CONFIRMING
    assert result_state.next_action is None
    assert result_state.review is not None
    assert result_state.review.summary == "计划结构清晰"
    assert "请确认是否采用" in response
    assert provider.complete.await_count == 2


def test_review_can_use_tool_and_return_to_review():
    definition = TOOL_REGISTRY[AvailableTool.LIST_USER_PROJECTS]
    original_handler = definition.handler
    handler = AsyncMock(return_value=[])
    object.__setattr__(definition, "handler", handler)

    provider = AsyncMock()
    provider.complete = AsyncMock(
        side_effect=[
            make_plan_decision(Action.REVIEW),
            make_review_decision(
                Action.USE_TOOL,
                tool_calls=[
                    ToolCall(
                        call_id="review-call",
                        tool_name=AvailableTool.LIST_USER_PROJECTS,
                        parameter={},
                    )
                ],
            ),
            make_review_decision(Action.CONFIRM),
        ]
    )
    flow = Flow(provider=provider)

    try:
        result_state, _ = asyncio.run(
            flow.run(make_state(), make_context())
        )
    finally:
        object.__setattr__(definition, "handler", original_handler)

    handler.assert_awaited_once()
    assert provider.complete.await_count == 3
    assert result_state.phase == AgentPhase.CONFIRMING
    assert result_state.tool_results[0].phase == AgentPhase.REVIEWING


def test_blocking_review_returns_to_plan_before_confirming():
    provider = AsyncMock()
    provider.complete = AsyncMock(
        side_effect=[
            make_plan_decision(Action.REVIEW),
            make_review_decision(
                Action.REPLAN,
                findings=[make_finding()],
            ),
            make_plan_decision(
                Action.REVIEW,
                content="已补充完成标准",
            ),
            make_review_decision(Action.CONFIRM),
        ]
    )
    flow = Flow(provider=provider)

    result_state, _ = asyncio.run(
        flow.run(make_state(), make_context())
    )

    assert provider.complete.await_count == 4
    assert result_state.revision_count == 1
    assert result_state.phase == AgentPhase.CONFIRMING


def test_flow_raises_when_step_limit_exceeded():
    provider = AsyncMock()
    provider.complete = AsyncMock(
        side_effect=[
            make_plan_decision(Action.REVIEW),
            make_review_decision(
                Action.REPLAN,
                findings=[make_finding()],
            ),
        ]
    )
    flow = Flow(provider=provider, max_steps=2)

    with pytest.raises(AgentFlowStepLimitExceededError):
        asyncio.run(flow.run(make_state(), make_context()))


def test_flow_executes_approved_plan_from_execute_entrypoint():
    execution = ExecutionResult(
        project_id=42,
        project_title="学习计划",
        created_task_count=1,
        completed_at=datetime.now(timezone.utc),
    )
    executor = SimpleNamespace(execute=AsyncMock(return_value=execution))
    provider = AsyncMock()
    provider.complete = AsyncMock()
    flow = Flow(provider=provider, executor=executor)
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        phase=AgentPhase.EXECUTING,
        human_decision=HumanDecision(approved=True),
        next_action=Action.EXECUTE,
        draft=PlanningDraft(
            project=PlanningProject(title="学习计划"),
            tasks=[PlanningTask(title="完成第一阶段学习")],
        ),
    )

    result_state, response = asyncio.run(
        flow.run(state, make_context())
    )

    executor.execute.assert_awaited_once()
    provider.complete.assert_not_awaited()
    assert result_state.phase == AgentPhase.COMPLETED
    assert result_state.next_action is None
    assert result_state.execution == execution
    assert "共写入 1 个任务" in response


def test_flow_rejects_state_without_next_action():
    provider = AsyncMock()
    provider.complete = AsyncMock()
    executor = SimpleNamespace(execute=AsyncMock())
    flow = Flow(provider=provider, executor=executor)
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        phase=AgentPhase.CONFIRMING,
        next_action=None,
    )

    with pytest.raises(AgentFlowEntryPointError):
        asyncio.run(flow.run(state, make_context()))

    provider.complete.assert_not_awaited()
    executor.execute.assert_not_awaited()
