from sqlalchemy.ext.asyncio import AsyncSession

from crud.project import (
    create_project_by_data,
    get_project_by_id_and_owner_user_id,
    get_projects_by_owner_user_id,
    update_project_by_data,
)
from crud.task import has_incomplete_project_tasks
from exceptions.project import (
    ArchivedProjectModificationError,
    EmptyProjectUpdateError,
    IncompleteProjectTasksError,
    InvalidProjectStatusTransitionError,
    InvalidProjectTimeRangeError,
    ProjectNotFoundError,
    SystemProjectModificationError,
)
from core.datetime_utils import utc_now_naive
from models.enums import CreationSource, ProjectStatus
from schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectStatusUpdate,
    ProjectUpdate,
)


ALLOWED_PROJECT_STATUS_TRANSITIONS = {
    ProjectStatus.PLANNING: {
        ProjectStatus.ACTIVE,
    },
    ProjectStatus.ACTIVE: {
        ProjectStatus.PAUSED,
        ProjectStatus.COMPLETED,
    },
    ProjectStatus.PAUSED: {
        ProjectStatus.ACTIVE,
        ProjectStatus.COMPLETED,
    },
    ProjectStatus.COMPLETED: {
        ProjectStatus.ACTIVE,
    },
}


async def create_project_for_user(
    project_create: ProjectCreate,
    user_id: int,
    db: AsyncSession,
) -> ProjectRead:
    data = project_create.model_dump()
    data["owner_user_id"] = user_id
    data["creation_source"] = CreationSource.MANUAL

    async with db.begin():
        project = await create_project_by_data(data, db)

    return ProjectRead.model_validate(project)


async def get_project_for_user(
    project_id: int,
    user_id: int,
    db: AsyncSession,
) -> ProjectRead:
    project = await get_project_by_id_and_owner_user_id(
        project_id,
        user_id,
        db,
    )
    if project is None:
        raise ProjectNotFoundError()

    return ProjectRead.model_validate(project)


async def get_projects_for_user(
    user_id: int,
    db: AsyncSession,
    archived: bool = False,
) -> list[ProjectRead]:
    projects = await get_projects_by_owner_user_id(
        user_id,
        db,
        archived,
    )
    return [ProjectRead.model_validate(project) for project in projects]


async def update_project_for_user(
    project_id: int,
    project_update: ProjectUpdate,
    user_id: int,
    db: AsyncSession,
) -> ProjectRead:
    update_data = project_update.model_dump(exclude_unset=True)
    if not update_data:
        raise EmptyProjectUpdateError()

    async with db.begin():
        project = await get_project_by_id_and_owner_user_id(
            project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

        if project.system_type is not None:
            raise SystemProjectModificationError()

        if project.archived_time is not None:
            raise ArchivedProjectModificationError()

        final_start_time = update_data.get(
            "start_time",
            project.start_time,
        )
        final_due_time = update_data.get(
            "due_time",
            project.due_time,
        )

        if (
            final_start_time is not None
            and final_due_time is not None
            and final_due_time < final_start_time
        ):
            raise InvalidProjectTimeRangeError()

        project = await update_project_by_data(
            project,
            update_data,
            db,
        )

    return ProjectRead.model_validate(project)


async def update_project_status_for_user(
    project_id: int,
    status_update: ProjectStatusUpdate,
    user_id: int,
    db: AsyncSession,
) -> ProjectRead:
    async with db.begin():
        project = await get_project_by_id_and_owner_user_id(
            project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

        if project.system_type is not None:
            raise SystemProjectModificationError()

        if project.archived_time is not None:
            raise ArchivedProjectModificationError()

        current_status = project.status
        target_status = status_update.status

        if current_status == target_status:
            return ProjectRead.model_validate(project)

        allowed_targets = ALLOWED_PROJECT_STATUS_TRANSITIONS[current_status]
        if target_status not in allowed_targets:
            raise InvalidProjectStatusTransitionError()

        if (
            target_status == ProjectStatus.COMPLETED
            and await has_incomplete_project_tasks(
                project.project_id,
                db,
            )
        ):
            raise IncompleteProjectTasksError()

        update_data: dict = {
            "status": target_status,
        }

        if target_status == ProjectStatus.COMPLETED:
            update_data["completed_time"] = utc_now_naive()
        elif current_status == ProjectStatus.COMPLETED:
            update_data["completed_time"] = None

        project = await update_project_by_data(
            project,
            update_data,
            db,
        )

    return ProjectRead.model_validate(project)


async def archive_project_for_user(
    project_id: int,
    user_id: int,
    db: AsyncSession,
) -> ProjectRead:
    async with db.begin():
        project = await get_project_by_id_and_owner_user_id(
            project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

        if project.system_type is not None:
            raise SystemProjectModificationError()

        if project.archived_time is None:
            project = await update_project_by_data(
                project,
                {"archived_time": utc_now_naive()},
                db,
            )

    return ProjectRead.model_validate(project)


async def restore_project_for_user(
    project_id: int,
    user_id: int,
    db: AsyncSession,
) -> ProjectRead:
    async with db.begin():
        project = await get_project_by_id_and_owner_user_id(
            project_id,
            user_id,
            db,
        )
        if project is None:
            raise ProjectNotFoundError()

        if project.system_type is not None:
            raise SystemProjectModificationError()

        if project.archived_time is not None:
            project = await update_project_by_data(
                project,
                {"archived_time": None},
                db,
            )

    return ProjectRead.model_validate(project)
