from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core.datetime_utils import utc_now_naive


class Base(DeclarativeBase):
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=utc_now_naive,
        nullable=False,
    )

    updated_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )