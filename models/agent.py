from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.user import User


class AgentSession(Base):
    __tablename__ = "agent_session"

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_json: Mapped[str] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions",
    )
