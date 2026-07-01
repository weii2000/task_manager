from pydantic import BaseModel, ConfigDict, Field
from schemas.user import UserRead


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    user: UserRead

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )