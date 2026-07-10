from datetime import datetime, timezone
from typing import Protocol

from agent.state import ExecutionResult, PlanningTask, State
from agent.tools.base import ToolContext
from core.datetime_utils import to_utc_naive
from crud.project import create_project_by_data
from crud.task import create_task_by_data
from exceptions.agent import AgentExecutionContextError
from models.enums import CreationSource, ProjectStatus, TaskStatus


class PlanExecutor(Protocol):
    async def execute(
        self,
        state: State,
        context: ToolContext,
    ) -> ExecutionResult:
        ...


class DatabasePlanExecutor:
    async def execute(
        self,
        state: State,
        context: ToolContext,
    ) -> ExecutionResult:
        if context.session_id is None:
            raise AgentExecutionContextError()
        if state.draft.project is None:
            raise AgentExecutionContextError("规划草稿缺少项目信息")
        if not state.draft.tasks:
            raise AgentExecutionContextError("规划草稿缺少可执行任务")

        planned_project = state.draft.project
        project = await create_project_by_data(
            {
                "owner_user_id": context.user_id,
                "title": planned_project.title,
                "description": planned_project.description,
                "goal": state.info.goal,
                "status": ProjectStatus.ACTIVE,
                "creation_source": CreationSource.AGENT,
                "start_time": self._to_database_time(
                    planned_project.start_time
                ),
                "due_time": self._to_database_time(
                    planned_project.due_time
                ),
                "source_agent_session_id": context.session_id,
            },
            context.db,
        )

        created_task_count = 0

        async def create_task_tree(
            planned_tasks: list[PlanningTask],
            parent_task_id: int | None = None,
        ) -> None:
            nonlocal created_task_count
            for sort_order, planned_task in enumerate(planned_tasks):
                task = await create_task_by_data(
                    {
                        "project_id": project.project_id,
                        "parent_task_id": parent_task_id,
                        "title": planned_task.title,
                        "description": planned_task.description,
                        "acceptance_criteria": (
                            planned_task.acceptance_criteria
                        ),
                        "sort_order": sort_order,
                        "priority": planned_task.priority,
                        "status": TaskStatus.TODO,
                        "creation_source": CreationSource.AGENT,
                        "start_time": self._to_database_time(
                            planned_task.start_time
                        ),
                        "due_time": self._to_database_time(
                            planned_task.due_time
                        ),
                    },
                    context.db,
                )
                created_task_count += 1
                await create_task_tree(
                    planned_task.subtasks,
                    parent_task_id=task.task_id,
                )

        await create_task_tree(state.draft.tasks)
        return ExecutionResult(
            project_id=project.project_id,
            project_title=project.title,
            created_task_count=created_task_count,
            executed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _to_database_time(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return to_utc_naive(value)
