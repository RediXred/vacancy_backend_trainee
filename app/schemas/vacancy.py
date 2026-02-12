from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class VacancyBase(BaseModel):
    title: str
    timetable_mode_name: str
    tag_name: str
    city_name: Optional[str] = None
    published_at: datetime
    is_remote_available: bool
    is_hot: bool

    @field_validator("published_at")
    @classmethod
    def date_not_in_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v > datetime.now(timezone.utc):
            raise ValueError("Published date cannot be in the future.")
        return v


class VacancyCreate(VacancyBase):
    external_id: int


class VacancyUpdate(VacancyBase):
    model_config = ConfigDict(extra="forbid")


class VacancyRead(VacancyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: int
    created_at: datetime
