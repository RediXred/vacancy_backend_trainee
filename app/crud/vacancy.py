from typing import Iterable, List, Optional

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacancy import Vacancy
from app.schemas.vacancy import VacancyCreate, VacancyUpdate


async def get_vacancy(session: AsyncSession, vacancy_id: int) -> Optional[Vacancy]:
    result = await session.execute(select(Vacancy).where(Vacancy.id == vacancy_id))
    return result.scalar_one_or_none()


async def get_vacancy_by_external_id(
    session: AsyncSession, external_id: int
) -> Optional[Vacancy]:
    result = await session.execute(
        select(Vacancy).where(Vacancy.external_id == external_id)
    )
    return result.scalar_one_or_none()


async def list_vacancies(
    session: AsyncSession,
    timetable_mode_name: Optional[str],
    city_name: Optional[str],
) -> List[Vacancy]:
    stmt: Select = select(Vacancy)
    if timetable_mode_name:
        stmt = stmt.where(Vacancy.timetable_mode_name.ilike(f"%{timetable_mode_name}%"))
    if city_name:
        stmt = stmt.where(Vacancy.city_name.ilike(f"%{city_name}%"))
    stmt = stmt.order_by(Vacancy.published_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_vacancy(session: AsyncSession, data: VacancyCreate) -> Vacancy:
    vacancy = Vacancy(**data.model_dump())
    session.add(vacancy)
    await session.commit()
    await session.refresh(vacancy)
    return vacancy


async def update_vacancy(
    session: AsyncSession, vacancy: Vacancy, data: VacancyUpdate
) -> Vacancy:
    for field, value in data.model_dump().items():
        setattr(vacancy, field, value)
    await session.commit()
    await session.refresh(vacancy)
    return vacancy


async def delete_vacancy(session: AsyncSession, vacancy: Vacancy) -> None:
    await session.delete(vacancy)
    await session.commit()


async def upsert_external_vacancies(
    session: AsyncSession, payloads: Iterable[dict]
) -> int:
    payloads = list(payloads)

    external_ids = [
        payload["external_id"]
        for payload in payloads
        if payload.get("external_id")
    ]

    if external_ids:
        result = await session.execute(
            select(Vacancy).where(Vacancy.external_id.in_(external_ids))
        )
        existing_vacancies = {
            v.external_id: v for v in result.scalars().all()
        }
    else:
        existing_vacancies = {}

    created_count = 0

    for payload in payloads:
        ext_id = payload.get("external_id")

        if ext_id and ext_id in existing_vacancies:
            vacancy = existing_vacancies[ext_id]
            for field, value in payload.items():
                setattr(vacancy, field, value)
        else:
            session.add(Vacancy(**payload))
            created_count += 1

    await session.commit()
    return created_count
