from pydantic import BaseModel, ConfigDict


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
    title: str
    description: str | None = None
    tag: str | None = None


class TaskCompleteUpdate(BaseModel):
    task_id: int
    completed: bool


class TaskInfoUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    tag: str | None = None


class TaskFilter(BaseModel):
    completed: bool | None = None
    tag: str | None = None