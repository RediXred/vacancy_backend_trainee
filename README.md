# Selectel Vacancies API

FastAPI-приложение для парсинга публичных вакансий Selectel, хранения в PostgreSQL и предоставления CRUD API.

## Быстрый старт

1. Клонируйте репозиторий (или распакуйте проект из архива):
   `git clone --branch with-bugs https://github.com/selectel/be-test.git`
2. Создайте `.env` на основе примера:
   `cp .env.example .env`
3. Примените переменные окружения `.env`:
   `source .env`
4. Запуск через Docker Desktop:
   `docker compose up --build`
5. Проверка работоспособности:
   откройте `http://localhost:8000/docs`
6. Остановка и очистка:
   `docker-compose down -v`

## Переменные окружения

- `DATABASE_URL` — строка подключения к PostgreSQL.
- `LOG_LEVEL` — уровень логирования (`INFO`, `DEBUG`).
- `PARSE_SCHEDULE_MINUTES` — интервал фонового парсинга в минутах.

## Основные эндпоинты

- `GET /api/v1/vacancies/` — список вакансий
- `GET /api/v1/vacancies/{id}` — детали вакансии.
- `POST /api/v1/vacancies/` — создание вакансии.
- `PUT /api/v1/vacancies/{id}` — обновление вакансии.
- `DELETE /api/v1/vacancies/{id}` — удаление вакансии.
- `POST /api/v1/parse/` — ручной запуск парсинга.

## Примечания

- При старте приложения выполняется первичный парсинг.
- Фоновый парсинг запускается планировщиком APScheduler (в рамках заданного интервала).

# Все баг-фисксы приведены в файле `fixed.md` в корне репозитория