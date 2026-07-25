from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.agent import AgentSession
    from models.auth import RefreshToken
    from models.memory import UserMemory
    from models.project import Project


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    bio: Mapped[str | None] = mapped_column(String(100), nullable=True)

    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", 
        back_populates="user"
    )
    sessions: Mapped[list["AgentSession"]] = relationship(
        "AgentSession",
        back_populates="user",
    )
    memories: Mapped[list["UserMemory"]] = relationship(
        "UserMemory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
