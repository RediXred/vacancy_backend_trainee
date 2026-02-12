from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@db:5432/postgres",
        validation_alias="DATABASE_URL",
    )

    api_url: str = "https://api.selectel.ru/proxy/public/employee/api/public/vacancies"

    log_level: str = "INFO"
    parse_schedule_minutes: int = Field(5, gt=0)
    vacancies_per_page: int = Field(10, gt=0)


settings = Settings()
