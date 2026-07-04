from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from core.datetime_utils import utc_now_naive
from core.security import create_access_token, create_refresh_token, decode_token, get_hashed_password, hash_token, verify
from crud.auth import create_refresh_token_record, get_refresh_token_by_token_hash, revoke_token_by_token_hash
from crud.project import create_project_by_data
from crud.user import create_user, get_user_by_user_id, get_user_by_username
from exceptions.auth import InvalidCredentialsError, InvalidRefreshTokenError
from exceptions.user import UsernameAlreadyExistsError
from models.enums import CreationSource, ProjectStatus, ProjectSystemType
from schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from schemas.user import UserRead


async def register(register_request: RegisterRequest, db: AsyncSession) -> tuple[AuthResponse, str]:
    try:
        async with db.begin():
            user = await get_user_by_username(register_request.username, db)
            if user:
                raise UsernameAlreadyExistsError()
            
            hashed_password = get_hashed_password(register_request.password)
            user = await create_user(register_request.username, hashed_password, db)

            await create_project_by_data(
                {
                    "owner_user_id": user.user_id,
                    "title": "Inbox",
                    "status": ProjectStatus.ACTIVE,
                    "creation_source": CreationSource.SYSTEM,
                    "system_type": ProjectSystemType.INBOX,
                },
                db,
            )

            access_token = create_access_token(str(user.user_id))
            refresh_token, expires_at = create_refresh_token(str(user.user_id))
            expires_at = expires_at.replace(tzinfo=None)
            token_hash = hash_token(refresh_token)
            await create_refresh_token_record(token_hash, expires_at, user.user_id, db)
            await db.refresh(user)
    except IntegrityError as exc:
        raise UsernameAlreadyExistsError() from exc

    return AuthResponse(access_token=access_token, user=UserRead.model_validate(user)), refresh_token # type: ignore


async def login(login_request: LoginRequest, db: AsyncSession) -> tuple[AuthResponse, str]:
    async with db.begin():
        user = await get_user_by_username(login_request.username, db)
        if not user or not verify(login_request.password, user.hashed_password):
            raise InvalidCredentialsError()
        
        access_token = create_access_token(str(user.user_id))
        refresh_token, expires_at = create_refresh_token(str(user.user_id))
        expires_at = expires_at.replace(tzinfo=None)
        token_hash = hash_token(refresh_token)
        await create_refresh_token_record(token_hash, expires_at, user.user_id, db)
        await db.refresh(user)

    return AuthResponse(access_token=access_token, user=UserRead.model_validate(user)), refresh_token # type: ignore


async def logout(refresh_token: str | None, db: AsyncSession):
    if refresh_token is None:
        raise InvalidRefreshTokenError()
    
    token_hash = hash_token(refresh_token)
    async with db.begin():
        await revoke_token_by_token_hash(token_hash, db)


async def refresh(refresh_token: str | None, db: AsyncSession):
    if refresh_token is None:
        raise InvalidRefreshTokenError()
    
    token_hash = hash_token(refresh_token)
    async with db.begin():
        old_refresh_token = await get_refresh_token_by_token_hash(token_hash, db)
        if old_refresh_token is None:
            raise InvalidRefreshTokenError()
        
        if old_refresh_token.expires_at <= utc_now_naive():
            raise InvalidRefreshTokenError()
        
        if old_refresh_token.revoked_at is not None:
            raise InvalidRefreshTokenError()
        
        subject = decode_token(refresh_token, "refresh")
        if subject is None:
            raise InvalidRefreshTokenError()

        try:
            user_id = int(subject)
        except (TypeError, ValueError) as exc:
            raise InvalidRefreshTokenError() from exc

        if user_id != old_refresh_token.user_id:
            raise InvalidRefreshTokenError()
        
        result = await revoke_token_by_token_hash(token_hash, db)
        if not result:
            raise InvalidRefreshTokenError()

        access_token = create_access_token(str(user_id))
        new_refresh_token, expires_at = create_refresh_token(str(user_id))
        expires_at = expires_at.replace(tzinfo=None)
        new_token_hash = hash_token(new_refresh_token)

        await create_refresh_token_record(new_token_hash, expires_at, user_id, db)
        user = await get_user_by_user_id(user_id, db)
        if user is None:
            raise InvalidRefreshTokenError()
    
    return AuthResponse(access_token=access_token, user=UserRead.model_validate(user)), new_refresh_token # type: ignore
