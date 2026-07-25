from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.user import User


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    refresh_token_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
