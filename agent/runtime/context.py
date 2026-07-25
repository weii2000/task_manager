"""Agent 运行上下文。"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import MemoryCategory


class RetrievedMemory(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_id: int = Field(gt=0)
    category: MemoryCategory
    content: str = Field(min_length=1, max_length=1000)


@dataclass(frozen=True)
class AgentRunContext:
    user_id: int
    db: AsyncSession
    session_id: int | None = None
    retrieved_memories: tuple[RetrievedMemory, ...] = ()
