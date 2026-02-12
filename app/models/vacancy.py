from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Vacancy(Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_vacancies_external_id"),
        CheckConstraint("published_at <= now()", name="check_published_at_not_future"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    timetable_mode_name: Mapped[str] = mapped_column(String, nullable=False)
    tag_name: Mapped[str] = mapped_column(String, nullable=False)
    city_name: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_remote_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_hot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
