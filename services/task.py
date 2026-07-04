from core.datetime_utils import utc_now_naive
from crud.project import (
    get_inbox_project_by_owner_user_id,
    get_project_by_id_and_owner_user_id,
)
from crud.task import (
    create_task_by_data,
    get_task_by_id_and_owner_user_id,
    get_tasks_by_project_id_and_owner_user_id,
    has_incomplete_child_tasks,
    has_unarchived_child_tasks,
    update_task_by_data,
)
from exceptions.project import ProjectNotFoundError
from exceptions.task import (
    ArchivedTaskModificationError,
    EmptyTaskUpdateError,
    InboxProjectNotFoundError,
    IncompleteChildTasksError,
    InvalidTaskStatusTransitionError,
    InvalidTaskTimeRangeError,
    ParentTaskProjectMismatchError,
    ParentTaskUnavailableError,
    ProjectUnavailableForTaskError,
    TaskHasUnarchivedChildrenError,
    TaskNotFoundError,
)
from models.enums import CreationSource, ProjectStatus, TaskStatus
from schemas.task import (
    TaskCreate,
    TaskRead,
    TaskStatusUpdate,
    TaskUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession


ALLOWED_TASK_STATUS_TRANSITIONS = {
    TaskStatus.TODO: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
    },
    TaskStatus.IN_PROGRESS: {
        TaskStatus.BLOCKED,
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
    },
    TaskStatus.BLOCKED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
    },
    TaskStatus.DONE: {
        TaskStatus.TODO,
    },
    TaskStatus.CANCELLED: {
        TaskStatus.TODO,
    },
}


async def create_task_for_user(
    task_create: TaskCreate,
    user_id: int,
    db: AsyncSession,
) -> TaskRead:
    task_data = task_create.model_dump()
    requested_project_id = task_data.pop("project_id")
    parent_task_id = task_data.get("parent_task_id")

    async with db.begin():
        parent_task = None

        if parent_task_id is not None:
            parent_task = await get_task_by_id_and_owner_user_id(
                parent_task_id,
                user_id,
                db,
            )
            if parent_task is None:
                raise TaskNotFoundError()
            if (
                parent_task.archived_time is not None
                or parent_task.status
                in {
                    TaskStatus.DONE,
                    TaskStatus.CANCELLED,
                }
            ):
                raise ParentTaskUnavailableError()

        if (
            parent_task is not None
            and requested_project_id is not None
            and parent_task.project_id != requested_project_id
        ):
            raise ParentTaskProjectMismatchError()

        resolved_project_id = requested_project_id

        if resolved_project_id is None and parent_task is not None:
            resolved_project_id = parent_task.project_id

        if resolved_project_id is None:
            project = await get_inbox_project_by_owner_user_id(
                user_id,
                db,
            )
            if project is None:
                raise InboxProjectNotFoundError()
        else:
            project = await get_project_by_id_and_owner_user_id(
                resolved_project_id,
                user_id,
                db,
            )
            if project is None:
                raise ProjectNotFoundError()

        if (
            project.archived_time is not None
            or project.status == ProjectStatus.COMPLETED
        ):
            raise ProjectUnavailableForTaskError()

        task_data["project_id"] = project.project_id
        task_data["creation_source"] = CreationSource.MANUAL

        task = await create_task_by_data(task_data, db)

    return TaskRead.model_validate(task)


async def get_task_for_user(
    task_id: int,
    user_id: int,
    db: AsyncSession,
) -> TaskRead:
    task = await get_task_by_id_and_owner_user_id(
        task_id,
        user_id,
        db,
    )
    if task is None:
        raise TaskNotFoundError()

    return TaskRead.model_validate(task)


async def get_project_tasks_for_user(
    user_id: int,
    db: AsyncSession,
    project_id: int | None = None,
    archived: bool = False,
) -> list[TaskRead]:
    if project_id is None:
        project = await get_inbox_project_by_owner_user_id(
            user_id,
            db,
        )
        if project is None:
            raise InboxProjectNotFoundError()
    else:
        project = await get_project_by_id_and_owner_user_id(
            project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

    tasks = await get_tasks_by_project_id_and_owner_user_id(
        project.project_id,
        user_id,
        db,
        archived,
    )

    return [TaskRead.model_validate(task) for task in tasks]


async def update_task_for_user(
    task_id: int,
    task_update: TaskUpdate,
    user_id: int,
    db: AsyncSession,
) -> TaskRead:
    update_data = task_update.model_dump(exclude_unset=True)
    if not update_data:
        raise EmptyTaskUpdateError()

    async with db.begin():
        task = await get_task_by_id_and_owner_user_id(
            task_id,
            user_id,
            db,
        )
        if task is None:
            raise TaskNotFoundError()

        if task.archived_time is not None:
            raise ArchivedTaskModificationError()

        project = await get_project_by_id_and_owner_user_id(
            task.project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

        if (
            project.archived_time is not None
            or project.status == ProjectStatus.COMPLETED
        ):
            raise ProjectUnavailableForTaskError()

        final_start_time = update_data.get(
            "start_time",
            task.start_time,
        )
        final_due_time = update_data.get(
            "due_time",
            task.due_time,
        )

        if (
            final_start_time is not None
            and final_due_time is not None
            and final_due_time < final_start_time
        ):
            raise InvalidTaskTimeRangeError()

        task = await update_task_by_data(
            task,
            update_data,
            db,
        )

    return TaskRead.model_validate(task)


async def update_task_status_for_user(
    task_id: int,
    status_update: TaskStatusUpdate,
    user_id: int,
    db: AsyncSession,
) -> TaskRead:
    async with db.begin():
        task = await get_task_by_id_and_owner_user_id(
            task_id,
            user_id,
            db,
        )
        if task is None:
            raise TaskNotFoundError()

        if task.archived_time is not None:
            raise ArchivedTaskModificationError()

        project = await get_project_by_id_and_owner_user_id(
            task.project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

        if (
            project.archived_time is not None
            or project.status == ProjectStatus.COMPLETED
        ):
            raise ProjectUnavailableForTaskError()

        current_status = task.status
        target_status = status_update.status

        if current_status == target_status:
            return TaskRead.model_validate(task)

        allowed_targets = ALLOWED_TASK_STATUS_TRANSITIONS[
            current_status
        ]
        if target_status not in allowed_targets:
            raise InvalidTaskStatusTransitionError()

        if (
            target_status == TaskStatus.DONE
            and await has_incomplete_child_tasks(task.task_id, db)
        ):
            raise IncompleteChildTasksError()

        update_data: dict = {
            "status": target_status,
        }

        if target_status == TaskStatus.DONE:
            update_data["completed_time"] = utc_now_naive()
        elif current_status == TaskStatus.DONE:
            update_data["completed_time"] = None

        task = await update_task_by_data(
            task,
            update_data,
            db,
        )

    return TaskRead.model_validate(task)


async def archive_task_for_user(
    task_id: int,
    user_id: int,
    db: AsyncSession,
) -> TaskRead:
    async with db.begin():
        task = await get_task_by_id_and_owner_user_id(
            task_id,
            user_id,
            db,
        )
        if task is None:
            raise TaskNotFoundError()

        if task.archived_time is not None:
            return TaskRead.model_validate(task)

        project = await get_project_by_id_and_owner_user_id(
            task.project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

        if (
            project.archived_time is not None
            or project.status == ProjectStatus.COMPLETED
        ):
            raise ProjectUnavailableForTaskError()

        if await has_unarchived_child_tasks(task.task_id, db):
            raise TaskHasUnarchivedChildrenError()

        task = await update_task_by_data(
            task,
            {"archived_time": utc_now_naive()},
            db,
        )

    return TaskRead.model_validate(task)


async def restore_task_for_user(
    task_id: int,
    user_id: int,
    db: AsyncSession,
) -> TaskRead:
    async with db.begin():
        task = await get_task_by_id_and_owner_user_id(
            task_id,
            user_id,
            db,
        )
        if task is None:
            raise TaskNotFoundError()

        if task.archived_time is None:
            return TaskRead.model_validate(task)

        project = await get_project_by_id_and_owner_user_id(
            task.project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

        if (
            project.archived_time is not None
            or project.status == ProjectStatus.COMPLETED
        ):
            raise ProjectUnavailableForTaskError()

        if task.parent_task_id is not None:
            parent_task = await get_task_by_id_and_owner_user_id(
                task.parent_task_id,
                user_id,
                db,
            )
            if (
                parent_task is None
                or parent_task.archived_time is not None
                or (
                    parent_task.status
                    in {
                        TaskStatus.DONE,
                        TaskStatus.CANCELLED,
                    }
                    and task.status
                    not in {
                        TaskStatus.DONE,
                        TaskStatus.CANCELLED,
                    }
                )
            ):
                raise ParentTaskUnavailableError()

        task = await update_task_by_data(
            task,
            {"archived_time": None},
            db,
        )

    return TaskRead.model_validate(task)
