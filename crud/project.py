from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import ProjectSystemType
from models.project import Project


async def create_project_by_data(
    project_data: dict,
    db: AsyncSession,
) -> Project:
    project = Project(**project_data)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


async def get_project_by_id_and_owner_user_id(
    project_id: int,
    owner_user_id: int,
    db: AsyncSession,
) -> Project | None:
    result = await db.execute(
        select(Project).where(
            Project.project_id == project_id,
            Project.owner_user_id == owner_user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_projects_by_owner_user_id(
    owner_user_id: int,
    db: AsyncSession,
    archived: bool = False,
    keyword: str | None = None,
) -> list[Project]:
    archive_condition = (
        Project.archived_time.is_not(None)
        if archived
        else Project.archived_time.is_(None)
    )
    conditions = [
        Project.owner_user_id == owner_user_id,
        archive_condition,
    ]

    if keyword:
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            pattern = f"%{normalized_keyword}%"
            conditions.append(
                or_(
                    Project.title.ilike(pattern),
                    Project.description.ilike(pattern),
                    Project.goal.ilike(pattern),
                )
            )

    result = await db.execute(
        select(Project)
        .where(*conditions)
        .order_by(Project.created_time.desc())
    )
    return list(result.scalars().all())


async def get_inbox_project_by_owner_user_id(
    owner_user_id: int,
    db: AsyncSession,
) -> Project | None:
    result = await db.execute(
        select(Project).where(
            Project.owner_user_id == owner_user_id,
            Project.system_type == ProjectSystemType.INBOX,
        )
    )
    return result.scalar_one_or_none()


async def update_project_by_data(
    project: Project,
    update_data: dict,
    db: AsyncSession,
) -> Project:
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)
    return project
