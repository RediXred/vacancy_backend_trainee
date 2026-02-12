# Отчёт по отладке приложения Серов Глеб Ильич

# Основные выявленные ошибки:
## Шаг 1: Первая попытка запуска
* Что сделал: запустил `docker compose up --build`, получил ошибку:
```bash
app-1 | pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings 
app-1 | database_url
```

* Проблема: опечатка в `core/config.py`, не совпадает с env:

* Решение: исправил опечатку `DATABSE_URL` -> `DATABASE_URL`

* Исходный код:
```python
database_url: str = Field(
    "postgresql+asyncpg://postgres:postgres@db:5432/postgres_typo",
    validation_alias="DATABSE_URL",
)
```

* Исправленный код:
```python
database_url: str = Field(
    "postgresql+asyncpg://postgres:postgres@db:5432/postgres",
    validation_alias="DATABASE_URL",
)
```

## Шаг 2: Вторая попытка запуска
* Что сделал: запустил `docker compose up --build`, получил ошибку:
```bash
app-1 | "city_name": item.city.name.strip()
app-1 | AttributeError: 'NoneType' object has no attribute 'name'
```

* Проблема: Приложение падает при попытке обратиться к полю `city.name` при Null (файл `services/parser.py`, функция `parse_and_store`).

* Решение: поле `city.name` может быть Null, поэтому `item.city.name.strip()` нужно использовать `getattr(item.city, "name", "").strip()`

* Исходный код:
```python
parsed_payloads.append(
    {
        "external_id": item.id,
        "title": item.title,
        "timetable_mode_name": item.timetable_mode.name,
        "tag_name": item.tag.name,
        "city_name": item.city.name.strip(),
        "published_at": item.published_at,
        "is_remote_available": item.is_remote_available,
        "is_hot": item.is_hot,
    }
)
```

* Исправленный код:
```python
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
```

# Шаг 3: Анализ исходного кода
* Что сделал: Сначала проанализировал, как происходит запрос к API в функции `parse_and_store` (файл `services/parser.py`). Обнаружил, что в коде создание клиента происходит без использования контекстного менеджера `async with` или явного вызова await `client.aclose()`. Это потенциально может привести к тому, что соединения оставались открытыми в пуле. При частом запуске парсера приложения могло исчерпать лимит файловых дескрипторов, что могло привести бы к ошибке `Too many open files`.

* Проблема: создание клиента без использования контекстного менеджера `async with` или явного вызова await `client.aclose()`

* Решение: использовать контекстный менеджер `async with`, чтобы дескрипторы соединений были автоматически закрыты.

* Исходный код:
```python
client = httpx.AsyncClient(timeout=timeout)
```

* Исправленный код:
```python
async with httpx.AsyncClient(timeout=timeout) as client:
```

# Шаг 4: Анализ схем данных
* Что сделал: Проанализировал базовую модель `VacancyBase` (`schemas/vacancy.py`) и обнаружил, что поле `external_id` было помечено как Optional. Поскольку это поле является критически важным бизнес-ключом для идентификации вакансий из внешнего API, его отсутствие во входящих данных привело бы к некорректной работе базы данных или ошибкам при попытке сопоставить существующие записи.

* Проблема: Поле `external_id` помечено как необязательное (Optional), что позволяет создавать или обновлять вакансии без указания внешнего идентификатора, нарушая целостность данных и логику синхронизации с внешним API.

* Решение: Пометить поле `external_id` как обязательное (убрать Optional)

* Исходный код:
```python
class VacancyBase(BaseModel):
    title: str
    timetable_mode_name: str
    tag_name: str
    city_name: Optional[str] = None
    published_at: datetime
    is_remote_available: bool
    is_hot: bool
    external_id: Optional[int] = None
```

* Исправленный код:
```python
class VacancyBase(BaseModel):
    title: str
    timetable_mode_name: str
    tag_name: str
    city_name: Optional[str] = None
    published_at: datetime
    is_remote_available: bool
    is_hot: bool
    external_id: int
```

# Шаг 5: Анализ ограничений целостности БД
* Что сделал: Проанализировал описание модели SQLAlchemy (`models/vacancy.py`) и обнаружил логическое противоречие между ограничением уникальности и настройками колонки `external_id`. В PostgreSQL ограничение UNIQUE игнорирует значения NULL. Это означает, что при `nullable=True` в таблицу можно было бы вставить неограниченное количество вакансий с "пустым" внешним идентификатором, что создает риск появления неидентифицируемых дубликатов.

* Проблема: Поле `external_id` помечено как `nullable=True` при наличии UniqueConstraint. Это позволяет обходить проверку на уникальность путем записи множественных значений NULL, что нарушает целостность данных в связке с внешним API.

* Решение: Установка `nullable=True`, убрать `None` из type_hint.

* Исходный код:
```python
__table_args__ = (UniqueConstraint("external_id", name="uq_vacancies_external_id"),)
external_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

* Исправленный код:
```python
__table_args__ = (UniqueConstraint("external_id", name="uq_vacancies_external_id"),)
external_id: Mapped[int] = mapped_column(Integer, nullable=False)
```

# Шаг 6: Анализ конфигурации планировщика
* Что сделал: Проанализировал инициализацию фоновой задачи в планировщике APScheduler (`services/scheduler.py`). Обнаружил критическую ошибку в сопоставлении единиц времени: переменная окружения, предназначенная для хранения интервала в минутах (`parse_schedule_minutes`), ошибочно передавалась в аргумент `seconds`.

* Проблема: Несоответствие размерности времени. Если в настройках указано "10" (10 минут), парсер запускался каждые 10 секунд. Также в `config.py` указано, что `parse_schedule_minutes` должно быть больше нуля.

* Решение: изменение параметра `seconds` на `minutes`.

* Исходный код:
```python
scheduler.add_job(
    job,
    trigger="interval",
    seconds=settings.parse_schedule_minutes,
    coalesce=True,
    max_instances=1,
)
```

* Исправленный код:
```python
scheduler.add_job(
    job,
    trigger="interval",
    minutes=settings.parse_schedule_minutes,
    coalesce=True,
    max_instances=1,
)
...
class Settings(BaseSettings):
    parse_schedule_minutes: int = Field(5, gt=0)
```

# Шаг 7: Анализ параметров запроса к внешнему API
* Что сделал: Проанализировал функцию `fetch_page`, отвечающую за получение данных от внешнего API Selectel (`services/parser.py`). Обнаружил использование магического числа 1000 в параметре `per_page`. При этом документация или фактическое поведение API часто ограничивает количество записей на одну страницу (например, до 10 или 50). Также параметр `API_URL` задан хардкодом в файле `services/parser.py`. Данный параметр был вынесен в конфигурацию окружения (`core/config.py`).

* Проблема: Хардкод параметра `per_page` со значением, превышающим лимиты API. Это вводило бы в заблуждение относительно объема получаемых данных и лишало возможности управлять нагрузкой на сеть через конфигурацию окружения.

* Решение: Используем конфигурацию окружения (`core/config.py`) для управления параметрами `per_page`, `API_URL`.

* Исходный код:
```python
async def fetch_page(client: httpx.AsyncClient, page: int) -> ExternalVacanciesResponse:
    response = await client.get(
        API_URL,
        params={"per_page": 1000, "page": page},
    )
    response.raise_for_status()
    return ExternalVacanciesResponse.model_validate(response.json())
```

* Исправленный код:
```python
class Settings(BaseSettings):
    vacancies_per_page: int = Field(10, gt=0)
    api_url: str = "https://api.selectel.ru/proxy/public/employee/api/public/vacancies"

...
async def fetch_page(client: httpx.AsyncClient, page: int) -> ExternalVacanciesResponse:
    response = await client.get(
        settings.api_url,
        params={"per_page": settings.vacancies_per_page, "page": page},
    )
    response.raise_for_status()
    return ExternalVacanciesResponse.model_validate(response.json())
```

# Шаг 8: Анализ логики обнаружения новых вакансий
* Что сделал: Проанализировал функцию `upsert_external_vacancies` (`crud/vacancy.py`), а именно блок инициализации множества существующих идентификаторов `existing_ids`. Обнаружил ошибку инициализации пустых коллекций: в ветке `else` переменной присваивался пустой словарь `{}` вместо пустого множества `set()`.

* Проблема: Несоответствие типов данных. Использование `{}` семантически некорректно и может привести к трудноуловимым багам (например, при попытке использовать методы множеств: union()/intersection()...)

* Решение: Исправил инициализацию множества `existing_ids`, теперь `set()`.

* Исходный код:
```python
if external_ids:
    existing_result = await session.execute(
        select(Vacancy.external_id).where(Vacancy.external_id.in_(external_ids))
    )
    existing_ids = set(existing_result.scalars().all())
else:
    existing_ids = {}
```

* Исправленный код:
```python
if external_ids:
    existing_result = await session.execute(
        select(Vacancy.external_id).where(Vacancy.external_id.in_(external_ids))
    )
    existing_ids = set(existing_result.scalars().all())
else:
    existing_ids = set()
```

# Шаг 8.1: Оптимизация производительности БД (Проблема N+1)
* Что сделал: Проанализировал функцию `upsert_external_vacancies` (`crud/vacancy.py`), отвечающую за синхронизацию данных с базой. Обнаружил классическую проблему N+1 запросов: код в цикле выполнял отдельный запрос к базе данных для каждой вакансии, чтобы получить её объект и обновить поля. Например, при обработке страницы из 100 вакансий это приводило к 100 последовательным обращениям к БД, что замедляло парсинг и создавало избыточную нагрузку на соединение.

* Проблема: Выполнение `select` внутри цикла. Это приводит к деградации производительности пропорционально количеству записей в пакете данных.

* Решение: Реализовал `Bulk Select`. Вместо того чтобы запрашивать каждую вакансию по отдельности, собираем все `external_id` из пакета данных и выполняем один единственный запрос к БД. Полученные результаты преобразуются в словарь для доступа по ID. Это сводит количество запросов к двум (один на чтение всех существующих и один commit на запись всех изменений), независимо от объема пакета.

* Исходный код:
```python
for payload in payloads:
    ext_id = payload["external_id"]
    if ext_id and ext_id in existing_ids:
        result = await session.execute(
            select(Vacancy).where(Vacancy.external_id == ext_id)
        )
```

* Исправленный код (работа с данными теперь в оперативной памяти, доступ через dict):
```python
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
```

# Шаг 9: Анализ обработки конфликтов данных
* Что сделал: Проанализировал логику эндпоинта `POST /vacancies/` (`api/v1/vacancies.py`). Обнаружил, что при попытке создать вакансию с уже существующим `external_id` сервер возвращал ответ со статусом 200, но с телом ошибки в формате JSON. Это является нарушением REST: статус 200 сообщает клиенту об успешной обработке, в то время как фактическая операция (создание ресурса) не была выполнена.

* Проблема: Использование некорректного HTTP-статуса при возникновении бизнес-ошибки. Возврат 200 при конфликте данных вводит в заблуждение клиентские приложения и системы автоматизированного тестирования, которые ориентируются на коды ответов.

* Решение: При совпадении `external_id` с существующей записью возвращается `409`.

* Исходный код
```python
@router.post("/", response_model=VacancyRead, status_code=status.HTTP_201_CREATED)
async def create_vacancy_endpoint(
    payload: VacancyCreate, session: AsyncSession = Depends(get_session)
) -> VacancyRead:
    if payload.external_id is not None:
        existing = await get_vacancy_by_external_id(session, payload.external_id)
        if existing:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"detail": "Vacancy with external_id already exists"},
            )
    return await create_vacancy(session, payload)
```

* Исправленный код (возврат 409 вместо 200):
```python
@router.post("/", response_model=VacancyRead, status_code=status.HTTP_201_CREATED)
async def create_vacancy_endpoint(
    payload: VacancyCreate, session: AsyncSession = Depends(get_session)
) -> VacancyRead:
    if payload.external_id is not None:
        existing = await get_vacancy_by_external_id(session, payload.external_id)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vacancy with this external_id already exists")
    return await create_vacancy(session, payload)
```

# Шаг 9.1: Анализ неизменяемости ключевых полей
* Что сделал: Проанализировал логику обновления вакансий через эндпоинт PUT (`api/v1/vacancies.py`). Обнаружил, что использование общей модели `VacancyBase` (`schemas/vacancy.py`) позволяло клиенту передавать поле `external_id` в запросе на обновление. Если переданный `external_id` уже принадлежал другой записи, база данных выбрасывала ошибку нарушения уникальности, что приводило к необработанному исключению и статусу 500.

* Проблема: Возможность изменения уникального внешнего идентификатора в запросе PUT. Это приводит к рассинхронизации данных с внешним источником, что нарушает бизнес-логику. 

* Решение: Изначально было принято решение, что `external_id` может меняться в PUT (при совпадении `external_id` с существующей записью возвращалось 409), но тогда возникает проблема, что при следующем парсинге эта же вакансия с Selectel снова парсилась в локальную БД. Поэтому принято решение, что пользователь не может менять `external_id` в PUT.

* Исходный код:
```python
@router.put("/{vacancy_id}", response_model=VacancyRead)
async def update_vacancy_endpoint(
    vacancy_id: int,
    payload: VacancyUpdate,
    session: AsyncSession = Depends(get_session),
) -> VacancyRead:
    vacancy = await get_vacancy(session, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return await update_vacancy(session, vacancy, payload)
```

* Исправленный код (перенесен external_id из VacancyBase в подклассы, чтобы нельзя было его менять в PUT):
```python
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
    def date_not_in_future(cls, v: datetime):
        if v.replace(tzinfo=None) > datetime.now().replace(tzinfo=None):
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
```

# Шаг 12: Соблюдение DRY
* Что сделал: Проанализировал структуру проекта и обнаружил дублирование кода зависимости `get_session`. Одна и та же корутина для генерации сессии базы данных была прописана вручную в разных модулях роутера (`api/v1/vacancies.py` и `api/v1/parse.py`).

* Проблема: Избыточное дублирование служебного кода. Это увеличивает риск возникновения ошибок при поддержке.

* Решение: Повторяющийся код вынесен в файл `api/deps.py`

* Нарушение DRY (`api/v1/vacancies.py` & `api/v1/parse.py`):
```python
async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
```

* Исправленный код:
Создан файл `api/deps.py` в который вынесена корутина `get_session`.


# Шаг 13: Порядок инициализации системы логирования
* Что сделал: Проанализировал `main.py` и обнаружил нарушение порядка инициализации компонентов. Вызов функции `setup_logging()`, которая настраивает формат вывода и уровни логов для всего приложения, происходил после создания экземпляра логгера и инициализации FastAPI.

* Проблема: Логгеры, созданные до вызова `setup_logging()`, инициализируются с настройками по умолчанию, игнорируя кастомную конфигурацию. Это могло привести к тому, что важные сообщения уровня INFO или DEBUG, отправленные в момент старта сервера или регистрации роутеров, просто не попадали в консоль или файлы.

* Решение: Исправленная последовательность инициализации

* Исходный код:
```python
logger = logging.getLogger(__name__)

app = FastAPI(title="Selectel Vacancies API")
app.include_router(api_router)

setup_logging()
```

* Исправленный код:
```python
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Selectel Vacancies API")
app.include_router(api_router)
```

# Шаг 14: Валидация даты публикации (published_at)
* Что сделал: Проанализировал процесс создания вакансий и обнаружил отсутствие контроля временных рамок для поля `published_at`. Система позволяла сохранять вакансии с датами из будущего, что противоречит бизнес-логике.

* Проблема: Отсутствие валидации даты публикации. Это позволяло записывать некорректные данные в БД (относительно бизнес-логики).

* Решение: Было создано ограничение даты публикации (`schemas/vacancy.py` & `models/vacancy.py`), чтобы она не могла быть в будущем (на уровне приложения и на уровне БД).

* Исходный код:
```python
class VacancyBase(BaseModel):
    title: str
    timetable_mode_name: str
    tag_name: str
    city_name: Optional[str] = None
    published_at: datetime
    is_remote_available: bool
    is_hot: bool
    external_id: int
```

* Исправленный код:
```python
__table_args__ = (
    UniqueConstraint("external_id", name="uq_vacancies_external_id"),
    CheckConstraint("published_at <= now()", name="check_published_at_not_future"),
)
...
class VacancyBase(BaseModel):
    title: str
    timetable_mode_name: str
    tag_name: str
    city_name: Optional[str] = None
    published_at: datetime
    is_remote_available: bool
    is_hot: bool
    external_id: int

    @field_validator("published_at")
    @classmethod
    def date_not_in_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v > datetime.now(timezone.utc):
            raise ValueError("Published date cannot be in the future.")
        return v
```

# Шаг 15: Обработка исключений и корректность возвращаемых данных
* Что сделал: Проанализировал блок обработки исключений в функции `parse_and_store` (`services/parser.py`). Обнаружил логическую ошибку, что при возникновении ошибки (например, таймаута на n-й странице) функция принудительно возвращала 0. Это упускало факт успешного сохранения данных с предыдущих страниц и дезинформировало пользователя о результатах работы.

* Проблема: Затирание прогресса при возникновении ошибки. Система сообщала о нулевом результате даже в тех случаях, когда база данных уже была успешно обновлена частью вакансий.

* Решение: Внедрена логика сохранения состояния. Теперь функция логирует контекст ошибки (номер страницы), но всегда возвращает актуальное количество обработанных записей `created_total`, накопленное до момента сбоя.

* Исходный код:
```python
except (httpx.RequestError, httpx.HTTPStatusError) as exc:
    logger.exception("Ошибка парсинга вакансий: %s", exc)
    return 0
```

* Исправленный код (вернули что успели сохранить):
```python
except (httpx.RequestError, httpx.HTTPStatusError) as exc:
    logger.error("Парсинг прерван на странице %s из-за ошибки: %s", page, exc)
    
except Exception as exc:
    logger.exception("Непредвиденная ошибка при обработке данных на странице %s", page)
    
logger.info("Парсинг завершен. Новых/обновленных вакансий: %s", created_total)
return created_total
```

# Шаг 16: Обогащение документации API
* Что сделал: Проанализировал автоматически генерируемую документацию `Swagger`. В ней отсутствовала информация о специфических кодах ошибок, которые может возвращать сервер (например, 409).

* Проблема: Неполная документация схем ответов. Без явного указания responses в декораторе эндпоинта, `Swagger` отображает только успешный код ответа и стандартные ошибки валидации, скрывая важную бизнес-логику обработки конфликтов.

* Решение: Добавил явное указание responses в декораторах эндпоинтов.

* Пример исправленного кода (`api/v1/vacancies.py`):
```python
@router.post("/", response_model=VacancyRead, status_code=status.HTTP_201_CREATED,
             responses={409: {"description": "Vacancy with this external_id already exists"}})
```

---
# Найденные ошибки/недочеты (итоговый список):
1) Утечка соединений HTTP-клиента
2) Падение при обработке Null-значений
3) Некорректная обработка исключений в парсере
4) Ошибка интервала планировщика
5) Противоречие в уникальности БД
6) Неверная конфигурация окружения
7) Некорректное использование HTTP-статуса
8) Неверная инициализация типов данных
9) Отсутствие контроля дат из будущего
10) Хардкод лимитов и URL API
11) Проблема N+1 запросов к базе
12) Конфликты при изменении external_id вакансий
13) Нарушение принципа DRY
14) Неправильный порядок инициализации логгера
15) Необязательный бизнес-ключ external_id в схемах
16) Неполная документация API

---
# Итог
* Исправлены критические баги: Устранены падения из-за пустых значений (NoneType) и сетевых ошибок.

* Оптимизирована производительность: Решена проблема N+1 запросов к БД.

* Обеспечена целостность данных: Установлены ограничения на уникальность ID и валидация дат.

* Настроен планировщик: Исправлена частота запусков парсера (минуты вместо секунд).

* Стандартизирован API: Исправлены HTTP-статусы, убрано дублирование кода (DRY) и дополнена документация Swagger.

* Настроена конфигурация и логи: Исправлены ошибки в переменных окружения и порядок инициализации логов.

* Ресурс-менеджмент: Исключены утечки соединений за счет использования контекстных менеджеров.

* Приложение стабилизировано и готово к работе (скриншоты приложены в директории screens, описание ниже).

---

## Использование ИИ
* ИИ использовался в качестве инструмента для поиска неочевидных проблем в коде, например, некорректный возврат из функции при исключении (шаг 15). Также ИИ использовался для объяснения кода из библиотеки APScheduler (просил объяснить внутренности методов `start()` & `shutdown()`, т.к. возникло недопонимание в сути их работы). В некоторых местах документации ИИ использовался для корректного обоснования проблем в коде, например про логгирование (шаг 13).

---

# Описание скриншотов

### cmd_out.png
![cmd_out.png](screens/cmd_out.png) - вывод логов docker-compose

### swagger.png
![swagger.png](screens/swagger.png) - документация API

### get_vacancies_1.png
![get_vacancies_1.png](screens/get_vacancies_1.png) - вывод всего списка вакансий

### get_vacancies_2.png
![get_vacancies_2.png](screens/get_vacancies_2.png) - вывод списка вакансий с `timetable_mode_name=Гибкий`

### get_vacancies_3.png
![get_vacancies_3.png](screens/get_vacancies_3.png) - вывод списка вакансий с `timetable_mode_name=Гибкий&city=Дубровка`

### get_vacancies_4.png
![get_vacancies_4.png](screens/get_vacancies_4.png) - вывод списка вакансий с `city=Дубровка`

### del_vacancies_1.png
![del_vacancies_1.png](screens/del_vacancies_1.png) - удаление вакансии с `vacancy_id=25`

### del_vacancies_2.png
![del_vacancies_2.png](screens/del_vacancies_2.png) - повторное удаление вакансии с `vacancy_id=25` (404)

### parse_vacancies_after_del.png
![parse_vacancies_after_del.png](screens/parse_vacancies_after_del.png) - парсинг вакансий после удаления (добавилась 1 вакансия, т.к. парсер спарсил вакансию с удаленной id=25)

### parse_vacancies_after_del_repeat.png
![parse_vacancies_after_del_repeat.png](screens/parse_vacancies_after_del_repeat.png) - повторное парсинг вакансий после удаления (`created: 0`)

### post_vacancies_1.png
![post_vacancies_1.png](screens/post_vacancies_1.png) - создание вакансии (корректно)

### post_vacancies_2.png
![post_vacancies_2.png](screens/post_vacancies_2.png) - повторное создание вакансии с тем же `external_id` (409)

### post_vacancies_3.png
![post_vacancies_3.png](screens/post_vacancies_3.png) - создание вакансии с некорректным `published_at` (422)

### put_vacancies_1.png
![put_vacancies_1.png](screens/put_vacancies_1.png) - обновление вакансии (корректно)

### put_vacancies_2.png
![put_vacancies_2.png](screens/put_vacancies_2.png) - создание вакансии с некорректным `published_at` (422)

### put_vacancies_3.png
![put_vacancies_3.png](screens/put_vacancies_3.png) - обновление вакансии с некорректным `vacancy_id` (404)

### put_vacancies_4.png
![put_vacancies_4.png](screens/put_vacancies_4.png) - обновление вакансии с указанием `external_id` (422)