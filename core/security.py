import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from core.config import settings

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_hashed_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": exp,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token(subject: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "type": "refresh",
        "jti": str(uuid4()),
        "iat": now,
        "exp": exp,
    }
    
    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return token, exp


def decode_token(token: str, require_type: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "type", "exp"]},
        )
    except InvalidTokenError:
        return None

    token_type = payload.get("type")

    if token_type != require_type:
        return None
    
    subject = payload.get("sub")

    if not isinstance(subject, str):
        return None

    return subject