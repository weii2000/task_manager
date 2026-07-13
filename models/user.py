from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


from models.base import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    bio: Mapped[str | None] = mapped_column(String(100), nullable=True)

    projects: Mapped[list["Project"]] = relationship( # type: ignore
        "Project",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship( # type: ignore
        "RefreshToken", 
        back_populates="user"
    )
    sessions: Mapped[list["AgentSession"]] = relationship( # type: ignore
        "AgentSession",
        back_populates="user",
    )
    memories: Mapped[list["UserMemory"]] = relationship(  # type: ignore
        "UserMemory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
