import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.vacancy import upsert_external_vacancies
from app.schemas.external import ExternalVacanciesResponse

logger = logging.getLogger(__name__)

async def fetch_page(client: httpx.AsyncClient, page: int) -> ExternalVacanciesResponse:
    response = await client.get(
        settings.api_url,
        params={"per_page": settings.vacancies_per_page, "page": page},
    )
    response.raise_for_status()
    return ExternalVacanciesResponse.model_validate(response.json())


async def parse_and_store(session: AsyncSession) -> int:
    logger.info("Старт парсинга вакансий")
    created_total = 0

    timeout = httpx.Timeout(10.0, read=20.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            page = 1
            while True:
                payload = await fetch_page(client, page)
                parsed_payloads = []
                for item in payload.items:
                    parsed_payloads.append(
                        {
                            "external_id": item.id,
                            "title": item.title,
                            "timetable_mode_name": item.timetable_mode.name,
                            "tag_name": item.tag.name,
                            "city_name": getattr(item.city, "name", "").strip() or None,
                            "published_at": item.published_at,
                            "is_remote_available": item.is_remote_available,
                            "is_hot": item.is_hot,
                        }
                    )

                created_count = await upsert_external_vacancies(session, parsed_payloads)
                created_total += created_count

                if page >= payload.page_count:
                    break
                page += 1
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.error("Парсинг прерван на странице %s из-за ошибки: %s", page, exc)
    
    except Exception as exc:
        logger.exception("Непредвиденная ошибка при обработке данных на странице %s", page)
    
    logger.info("Парсинг завершен. Новых/обновленных вакансий: %s", created_total)
    return created_total
