from fastapi import APIRouter

from app.api.v1.parse import router as parse_router
from app.api.v1.vacancies import router as vacancies_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(vacancies_router)
api_router.include_router(parse_router)
