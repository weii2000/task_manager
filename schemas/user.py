from pydantic import BaseModel, ConfigDict, Field, EmailStr


class UserInfoUpdate(BaseModel):
    email: EmailStr | None = Field(default=None, description="邮箱地址",)
    bio: str | None = Field(default=None, max_length=500, description="个人简介",)


class UserRead(BaseModel):
    username: str
    email: EmailStr | None = Field(default=None, description="邮箱地址",)
    bio: str | None = Field(default=None, description="个人简介",)

    model_config = ConfigDict(from_attributes=True)
