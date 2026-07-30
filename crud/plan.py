from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import PlanSystemType
from models.plan import Plan


async def create_plan_by_data(
    plan_data: dict,
    db: AsyncSession,
) -> Plan:
    plan = Plan(**plan_data)
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


async def get_plan_by_id_and_owner_user_id(
    plan_id: int,
    owner_user_id: int,
    db: AsyncSession,
) -> Plan | None:
    result = await db.execute(
        select(Plan).where(
            Plan.plan_id == plan_id,
            Plan.owner_user_id == owner_user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_plan_by_idempotency_key(
    owner_user_id: int,
    idempotency_key: str,
    db: AsyncSession,
) -> Plan | None:
    result = await db.execute(
        select(Plan).where(
            Plan.owner_user_id == owner_user_id,
            Plan.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def get_plans_by_owner_user_id(
    owner_user_id: int,
    db: AsyncSession,
    archived: bool = False,
    keyword: str | None = None,
) -> list[Plan]:
    archive_condition = (
        Plan.archived_time.is_not(None)
        if archived
        else Plan.archived_time.is_(None)
    )
    conditions = [
        Plan.owner_user_id == owner_user_id,
        archive_condition,
    ]

    if keyword:
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            pattern = f"%{normalized_keyword}%"
            conditions.append(
                or_(
                    Plan.title.ilike(pattern),
                    Plan.description.ilike(pattern),
                    Plan.goal.ilike(pattern),
                )
            )

    result = await db.execute(
        select(Plan)
        .where(*conditions)
        .order_by(Plan.created_time.desc())
    )
    return list(result.scalars().all())


async def get_inbox_plan_by_owner_user_id(
    owner_user_id: int,
    db: AsyncSession,
) -> Plan | None:
    result = await db.execute(
        select(Plan).where(
            Plan.owner_user_id == owner_user_id,
            Plan.system_type == PlanSystemType.INBOX,
        )
    )
    return result.scalar_one_or_none()


async def update_plan_by_data(
    plan: Plan,
    update_data: dict,
    db: AsyncSession,
) -> Plan:
    for field, value in update_data.items():
        setattr(plan, field, value)

    await db.flush()
    await db.refresh(plan)
    return plan
