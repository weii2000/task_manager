import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from agent.runtime.context import AgentRunContext
from agent.runtime.state import (
    Message,
    MessageRole,
    PlanningDraft,
    PlanningInfo,
    PlanningPlan,
    PlanningTask,
    State,
)
from exceptions.agent import AgentExecutionContextError
from models.enums import TaskPriority
from schemas.plan_tree import PlanResult
from services.plan_execution import persist_plan


def make_state() -> State:
    return State(
        messages=[Message(role=MessageRole.USER, content="创建学习计划")],
        info=PlanningInfo(goal="完成 Agent 工程学习"),
        draft=PlanningDraft(
            plan=PlanningPlan(
                title="Agent 工程学习",
                description="通过项目完成学习闭环",
                start_time=datetime(
                    2026,
                    7,
                    12,
                    10,
                    tzinfo=timezone(timedelta(hours=8)),
                ),
            ),
            tasks=[
                PlanningTask(
                    title="完成基础实现",
                    priority=TaskPriority.HIGH,
                    subtasks=[
                        PlanningTask(
                            title="补齐测试",
                            acceptance_criteria="关键路径测试通过",
                        )
                    ],
                ),
                PlanningTask(title="整理文档"),
            ],
        ),
    )


def test_persist_plan_creates_plan_and_task_tree(monkeypatch):
    persist_plan_tree = AsyncMock(
        return_value=PlanResult(
            plan_id=42,
            plan_title="Agent 工程学习",
            created_task_count=3,
        )
    )
    monkeypatch.setattr(
        "services.plan_execution.persist_plan_tree",
        persist_plan_tree,
    )
    db = AsyncMock()
    context = AgentRunContext(user_id=7, db=db, session_id=9)

    result = asyncio.run(
        persist_plan(make_state(), context)
    )

    plan = persist_plan_tree.await_args.args[0]
    assert plan.goal == "完成 Agent 工程学习"
    assert plan.start_time == datetime(2026, 7, 12, 2)
    assert plan.tasks[0].priority == TaskPriority.HIGH
    assert plan.tasks[0].level == 1
    assert plan.tasks[0].subtasks[0].level == 2
    assert plan.tasks[0].subtasks[0].title == "补齐测试"
    assert persist_plan_tree.await_args.args[1:] == (
        "agent-session:9",
        7,
        db,
    )
    assert (
        persist_plan_tree.await_args.kwargs[
            "source_agent_session_id"
        ]
        == 9
    )
    assert result.plan_id == 42
    assert result.created_task_count == 3


def test_persist_plan_requires_session_context():
    context = AgentRunContext(user_id=7, db=AsyncMock())

    with pytest.raises(AgentExecutionContextError):
        asyncio.run(persist_plan(make_state(), context))


def test_persist_plan_rejects_empty_task_plan():
    state = make_state()
    state.draft.tasks = []
    context = AgentRunContext(user_id=7, db=AsyncMock(), session_id=9)

    with pytest.raises(AgentExecutionContextError):
        asyncio.run(persist_plan(state, context))
