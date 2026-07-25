import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.user import UserRead

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError("Username can only contain English letters, numbers, and underscores")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value):
            raise ValueError("Password must contain at least one letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number")
        return value

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    user: UserRead

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )