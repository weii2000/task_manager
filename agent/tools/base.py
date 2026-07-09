from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolContext:
    user_id: int
    db: AsyncSession


ToolHandler = Callable[
    [ToolContext, dict[str, Any]],
    Awaitable[Any],
]
