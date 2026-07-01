from sqlalchemy.ext.asyncio import AsyncSession


from crud.user import update_user_info_by_dict
from exceptions.user import EmptyUserUpdateError, UserNotFoundError
from schemas.user import UserInfoUpdate, UserRead


async def update_user_info(user_info_update: UserInfoUpdate, user_id: int, db: AsyncSession) -> UserRead:
    update_data = user_info_update.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        raise EmptyUserUpdateError()

    async with db.begin():
        user = await update_user_info_by_dict(update_data, user_id, db)
        if not user:
            raise UserNotFoundError()

    await db.refresh(user)
    return UserRead.model_validate(user)
