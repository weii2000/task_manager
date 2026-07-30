from sqlalchemy.ext.asyncio import AsyncSession

from core.datetime_utils import utc_now_naive
from crud.plan import (
    create_plan_by_data,
    get_plan_by_id_and_owner_user_id,
    get_plans_by_owner_user_id,
    update_plan_by_data,
)
from crud.task import has_incomplete_plan_tasks
from exceptions.plan import (
    ArchivedPlanModificationError,
    EmptyPlanUpdateError,
    IncompletePlanTasksError,
    InvalidPlanStatusTransitionError,
    InvalidPlanTimeRangeError,
    PlanNotFoundError,
    SystemPlanModificationError,
)
from models.enums import CreationSource, PlanStatus
from schemas.plan import (
    PlanCreate,
    PlanRead,
    PlanStatusUpdate,
    PlanUpdate,
)

ALLOWED_PLAN_STATUS_TRANSITIONS = {
    PlanStatus.PLANNING: {
        PlanStatus.ACTIVE,
    },
    PlanStatus.ACTIVE: {
        PlanStatus.PAUSED,
        PlanStatus.COMPLETED,
    },
    PlanStatus.PAUSED: {
        PlanStatus.ACTIVE,
        PlanStatus.COMPLETED,
    },
    PlanStatus.COMPLETED: {
        PlanStatus.ACTIVE,
    },
}


async def create_plan_for_user(
    plan_create: PlanCreate,
    user_id: int,
    db: AsyncSession,
) -> PlanRead:
    data = plan_create.model_dump()
    data["owner_user_id"] = user_id
    data["creation_source"] = CreationSource.MANUAL

    async with db.begin():
        plan = await create_plan_by_data(data, db)

    return PlanRead.model_validate(plan)


async def get_plan_for_user(
    plan_id: int,
    user_id: int,
    db: AsyncSession,
) -> PlanRead:
    plan = await get_plan_by_id_and_owner_user_id(
        plan_id,
        user_id,
        db,
    )
    if plan is None:
        raise PlanNotFoundError()

    return PlanRead.model_validate(plan)


async def get_plans_for_user(
    user_id: int,
    db: AsyncSession,
    archived: bool = False,
    keyword: str | None = None,
) -> list[PlanRead]:
    plans = await get_plans_by_owner_user_id(
        user_id,
        db,
        archived,
        keyword,
    )
    return [PlanRead.model_validate(plan) for plan in plans]


async def update_plan_for_user(
    plan_id: int,
    plan_update: PlanUpdate,
    user_id: int,
    db: AsyncSession,
) -> PlanRead:
    update_data = plan_update.model_dump(exclude_unset=True)
    if not update_data:
        raise EmptyPlanUpdateError()

    async with db.begin():
        plan = await get_plan_by_id_and_owner_user_id(
            plan_id,
            user_id,
            db,
        )
        if plan is None:
            raise PlanNotFoundError()

        if plan.system_type is not None:
            raise SystemPlanModificationError()

        if plan.archived_time is not None:
            raise ArchivedPlanModificationError()

        final_start_time = update_data.get(
            "start_time",
            plan.start_time,
        )
        final_due_time = update_data.get(
            "due_time",
            plan.due_time,
        )

        if (
            final_start_time is not None
            and final_due_time is not None
            and final_due_time < final_start_time
        ):
            raise InvalidPlanTimeRangeError()

        plan = await update_plan_by_data(
            plan,
            update_data,
            db,
        )

    return PlanRead.model_validate(plan)


async def update_plan_status_for_user(
    plan_id: int,
    status_update: PlanStatusUpdate,
    user_id: int,
    db: AsyncSession,
) -> PlanRead:
    async with db.begin():
        plan = await get_plan_by_id_and_owner_user_id(
            plan_id,
            user_id,
            db,
        )
        if plan is None:
            raise PlanNotFoundError()

        if plan.system_type is not None:
            raise SystemPlanModificationError()

        if plan.archived_time is not None:
            raise ArchivedPlanModificationError()

        current_status = plan.status
        target_status = status_update.status

        if current_status == target_status:
            return PlanRead.model_validate(plan)

        allowed_targets = ALLOWED_PLAN_STATUS_TRANSITIONS[current_status]
        if target_status not in allowed_targets:
            raise InvalidPlanStatusTransitionError()

        if (
            target_status == PlanStatus.COMPLETED
            and await has_incomplete_plan_tasks(
                plan.plan_id,
                db,
            )
        ):
            raise IncompletePlanTasksError()

        update_data: dict = {
            "status": target_status,
        }

        if target_status == PlanStatus.COMPLETED:
            update_data["completed_time"] = utc_now_naive()
        elif current_status == PlanStatus.COMPLETED:
            update_data["completed_time"] = None

        plan = await update_plan_by_data(
            plan,
            update_data,
            db,
        )

    return PlanRead.model_validate(plan)


async def archive_plan_for_user(
    plan_id: int,
    user_id: int,
    db: AsyncSession,
) -> PlanRead:
    async with db.begin():
        plan = await get_plan_by_id_and_owner_user_id(
            plan_id,
            user_id,
            db,
        )
        if plan is None:
            raise PlanNotFoundError()

        if plan.system_type is not None:
            raise SystemPlanModificationError()

        if plan.archived_time is None:
            plan = await update_plan_by_data(
                plan,
                {"archived_time": utc_now_naive()},
                db,
            )

    return PlanRead.model_validate(plan)


async def restore_plan_for_user(
    plan_id: int,
    user_id: int,
    db: AsyncSession,
) -> PlanRead:
    async with db.begin():
        plan = await get_plan_by_id_and_owner_user_id(
            plan_id,
            user_id,
            db,
        )
        if plan is None:
            raise PlanNotFoundError()

        if plan.system_type is not None:
            raise SystemPlanModificationError()

        if plan.archived_time is not None:
            plan = await update_plan_by_data(
                plan,
                {"archived_time": None},
                db,
            )

    return PlanRead.model_validate(plan)
