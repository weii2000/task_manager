from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from agent.runtime.state import (
    Action,
    AgentPhase,
    ExecutionResult,
    Message,
    MessageRole,
    PlanDecision,
    PlanningDraft,
    PlanningProject,
    PlanningTask,
    State,
)


def test_planning_project_normalizes_time_to_utc_and_survives_round_trip():
    china_time = timezone(timedelta(hours=8))

    project = PlanningProject(
        title="学习计划",
        start_time=datetime(2026, 7, 12, 10, tzinfo=china_time),
    )

    assert project.start_time == datetime(
        2026,
        7,
        12,
        2,
        tzinfo=timezone.utc,
    )
    assert PlanningProject.model_validate_json(
        project.model_dump_json()
    ) == project


def test_planning_project_rejects_time_without_timezone():
    with pytest.raises(ValidationError):
        PlanningProject(
            title="学习计划",
            start_time=datetime(2026, 7, 12, 10),
        )


def test_review_action_requires_executable_project_and_tasks():
    with pytest.raises(ValidationError):
        PlanDecision(
            content="提交评审",
            next_action=Action.REVIEW,
            draft=PlanningDraft(tasks=[PlanningTask(title="任务")]),
        )


def test_planning_draft_rejects_task_tree_deeper_than_six_levels():
    task = PlanningTask(title="第七层")
    for depth in range(6, 0, -1):
        task = PlanningTask(title=f"第 {depth} 层", subtasks=[task])

    with pytest.raises(ValidationError):
        PlanningDraft(
            project=PlanningProject(title="学习计划"),
            tasks=[task],
        )


def test_planning_draft_accepts_six_task_levels():
    task = PlanningTask(title="第六层")
    for depth in range(5, 0, -1):
        task = PlanningTask(title=f"第 {depth} 层", subtasks=[task])

    draft = PlanningDraft(
        project=PlanningProject(title="学习计划"),
        tasks=[task],
    )

    assert draft.tasks[0].subtasks[0].title == "第 2 层"


def test_state_rejects_action_incompatible_with_phase():
    with pytest.raises(ValidationError):
        State(
            messages=[Message(role=MessageRole.USER, content="开始规划")],
            phase=AgentPhase.EXECUTING,
            next_action=Action.PLAN,
        )


def test_completed_state_requires_execution_result():
    with pytest.raises(ValidationError):
        State(
            messages=[Message(role=MessageRole.USER, content="开始规划")],
            phase=AgentPhase.COMPLETED,
            next_action=None,
        )


def test_execution_result_is_only_allowed_in_completed_state():
    execution = ExecutionResult(
        project_id=42,
        project_title="学习计划",
        created_task_count=1,
        completed_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ValidationError):
        State(
            messages=[Message(role=MessageRole.USER, content="开始规划")],
            phase=AgentPhase.PLANNING,
            next_action=None,
            execution=execution,
        )
