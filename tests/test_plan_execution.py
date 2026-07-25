import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.runtime.context import AgentRunContext
from agent.runtime.state import (
    Message,
    MessageRole,
    PlanningDraft,
    PlanningInfo,
    PlanningProject,
    PlanningTask,
    State,
)
from exceptions.agent import AgentExecutionContextError
from models.enums import CreationSource, ProjectStatus, TaskPriority, TaskStatus
from services.plan_execution import persist_plan


def make_state() -> State:
    return State(
        messages=[Message(role=MessageRole.USER, content="创建学习计划")],
        info=PlanningInfo(goal="完成 Agent 工程学习"),
        draft=PlanningDraft(
            project=PlanningProject(
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


def test_persist_plan_creates_project_and_task_tree(monkeypatch):
    project = SimpleNamespace(project_id=42, title="Agent 工程学习")
    tasks = [
        SimpleNamespace(task_id=101),
        SimpleNamespace(task_id=102),
        SimpleNamespace(task_id=103),
    ]
    create_project = AsyncMock(return_value=project)
    create_task = AsyncMock(side_effect=tasks)
    monkeypatch.setattr(
        "services.plan_execution.create_project_by_data",
        create_project,
    )
    monkeypatch.setattr(
        "services.plan_execution.create_task_by_data",
        create_task,
    )
    db = AsyncMock()
    context = AgentRunContext(user_id=7, db=db, session_id=9)

    result = asyncio.run(
        persist_plan(make_state(), context)
    )

    project_data = create_project.await_args.args[0]
    assert project_data["owner_user_id"] == 7
    assert project_data["source_agent_session_id"] == 9
    assert project_data["status"] == ProjectStatus.ACTIVE
    assert project_data["creation_source"] == CreationSource.AGENT
    assert project_data["goal"] == "完成 Agent 工程学习"
    assert project_data["start_time"] == datetime(2026, 7, 12, 2)

    task_calls = create_task.await_args_list
    assert len(task_calls) == 3
    first_task = task_calls[0].args[0]
    child_task = task_calls[1].args[0]
    second_task = task_calls[2].args[0]
    assert first_task["parent_task_id"] is None
    assert first_task["sort_order"] == 0
    assert first_task["priority"] == TaskPriority.HIGH
    assert first_task["status"] == TaskStatus.TODO
    assert first_task["creation_source"] == CreationSource.AGENT
    assert child_task["parent_task_id"] == 101
    assert child_task["sort_order"] == 0
    assert child_task["acceptance_criteria"] == "关键路径测试通过"
    assert second_task["parent_task_id"] is None
    assert second_task["sort_order"] == 1
    assert result.project_id == 42
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
