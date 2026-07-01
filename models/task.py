from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


from models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tag: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="tasks") # type: ignore
