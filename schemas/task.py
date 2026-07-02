from pydantic import BaseModel, ConfigDict, Field


class TaskRead(BaseModel):
    task_id: int
    title: str
    description: str | None = None
    completed: bool
    tag: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class TaskCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="任务标题",
    )

    description: str | None = Field(
        default=None,
        max_length=500,
        description="任务描述",
    )

    tag: str | None = Field(
        default=None,
        max_length=50,
        description="任务标签",
    )


class TaskCompleteUpdate(BaseModel):
    task_id: int
    completed: bool


class TaskInfoUpdate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="任务标题",
    )

    description: str | None = Field(
        default=None,
        max_length=500,
        description="任务描述",
    )

    tag: str | None = Field(
        default=None,
        max_length=50,
        description="任务标签",
    )
