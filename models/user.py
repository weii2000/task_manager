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

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user") # type: ignore
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship("RefreshToken", back_populates="user") # type: ignore