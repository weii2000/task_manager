from pydantic import BaseModel, ConfigDict, Field


class UserInfoUpdate(BaseModel):
    email: str | None = None
    bio: str | None = None


class UserRead(BaseModel):
    username: str
    email: str | None = None
    bio: str | None = None

    model_config = ConfigDict(from_attributes=True)
