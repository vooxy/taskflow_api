# TaskFlow API

![CI](https://github.com/vooxy/taskflow_api/actions/workflows/ci.yml/badge.svg)

REST API для управления задачами команды.

**Стек:** Python 3.12, FastAPI, PostgreSQL 16, SQLAlchemy 2, Alembic, Docker Compose.

## Запуск

Нужен только Docker (Docker Desktop на Windows/macOS).

```bash
git clone https://github.com/vooxy/taskflow_api.git
cd taskflow_api
docker compose up --build
```

При старте контейнер `api` ждёт готовности PostgreSQL, применяет миграции (`alembic upgrade head`) и запускает сервер.

- API: http://localhost:8000
- Документация Swagger: http://localhost:8000/docs
- Проверка работы: http://localhost:8000/health

Файл `.env` не обязателен: без него используются значения по умолчанию. Чтобы задать свой пароль БД, скопируйте `.env.example` в `.env` и отредактируйте его.

Остановка (данные сохраняются в volume `pgdata`):

```bash
docker compose down
```

Полный сброс вместе с данными БД:

```bash
docker compose down -v
```

## Ресурсы

Для `users`, `projects`, `labels`, `tasks`, `comments` доступны:

| Метод | URL | Результат | Код |
|---|---|---|---|
| `GET` | `/v1/{resource}` | список записей | 200 |
| `GET` | `/v1/{resource}/{id}` | одна запись | 200 / 404 |
| `POST` | `/v1/{resource}` | создание | 201 |
| `PATCH` | `/v1/{resource}/{id}` | частичное обновление | 200 / 404 |
| `DELETE` | `/v1/{resource}/{id}` | удаление | 204 / 404 |

Фильтры:

- `GET /v1/tasks?project_id=1&status=open`
- `GET /v1/comments?task_id=1`

Ошибки:

- `422`: неверные входные данные, например неизвестный статус, неверный email или цвет, служебное поле `id` в теле;
- `404`: запись не найдена;
- `409`: дубликат уникального значения (`users.email`, `labels.name`), ссылка на несуществующую запись или удаление пользователя, у которого есть комментарии.

Правила удаления (на уровне БД):

- удаление проекта удаляет его задачи, а вместе с ними и комментарии к ним (`CASCADE`);
- удаление задачи удаляет её комментарии (`CASCADE`);
- удаление пользователя или метки обнуляет `assignee_id` / `label_id` в задачах (`SET NULL`);
- пользователя с комментариями удалить нельзя (`RESTRICT` → `409`).

## Примеры запросов

Проверка соединения с БД:

```bash
curl http://localhost:8000/health
# {"status":"ok","database":"up"}
```

Создание пользователя:

```bash
curl -X POST http://localhost:8000/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email": "karim@example.com", "display_name": "Karim"}'
```

Создание проекта, метки и задачи:

```bash
curl -X POST http://localhost:8000/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Backend course", "description": "Практика по FastAPI"}'

curl -X POST http://localhost:8000/v1/labels \
  -H "Content-Type: application/json" \
  -d '{"name": "bug", "color": "#ef4444"}'

curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "assignee_id": 1, "label_id": 1, "title": "Сделать CRUD", "priority": "high"}'
```

Комментарий к задаче:

```bash
curl -X POST http://localhost:8000/v1/comments \
  -H "Content-Type: application/json" \
  -d '{"task_id": 1, "author_id": 1, "body": "Начинаю работу"}'
```

Фильтр задач и смена статуса:

```bash
curl "http://localhost:8000/v1/tasks?project_id=1&status=open"

curl -X PATCH http://localhost:8000/v1/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "done"}'
```

> В Windows PowerShell вместо `curl` удобнее использовать Swagger UI по адресу `/docs`.

## Миграции

Схема БД создаётся только миграциями Alembic (`alembic/versions/0001_create_initial_schema.py`). `create_all()` в приложении не используется. Alembic берёт адрес БД из переменной окружения `DATABASE_URL`.

Проверка миграций внутри запущенного контейнера:

```bash
docker compose exec api alembic downgrade base
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

## Логирование

Уровень логов задаётся переменной окружения `LOG_LEVEL`: `DEBUG`, `INFO` (по умолчанию), `WARNING`, `ERROR`, `CRITICAL`. Регистр не важен.

```bash
LOG_LEVEL=DEBUG docker compose up --build
```

В Windows PowerShell проще задать `LOG_LEVEL=DEBUG` в файле `.env`.

| Уровень | Что пишется |
|---|---|
| `DEBUG` | открытие и закрытие сессии БД, начало запроса, параметры фильтров |
| `INFO` | запуск и остановка, каждый запрос (метод, путь, код, время), создание, изменение и удаление записей |
| `WARNING` | ошибки клиента: `404`, `409`, `422` |
| `ERROR` | сбои сервера: БД недоступна в `/health` (`503`), необработанное исключение (`500`) |
| `CRITICAL` | API запустился, но база данных недоступна |

Пример вывода:

```text
2026-11-07 12:00:00,123 INFO     app.main: Starting TaskFlow API (log level INFO)
2026-11-07 12:00:05,456 INFO     app.routers.tasks: Task 1 created
2026-11-07 12:00:05,457 INFO     app.main: POST /v1/tasks -> 201 (12.3 ms)
2026-11-07 12:00:07,890 WARNING  app.main: GET /v1/tasks/99 -> 404: Task not found
```

## Тесты

Тесты написаны на `pytest` и разделены на четыре вида (каталог `tests/`):

| Папка | Маркер | Что проверяет |
|---|---|---|
| `tests/unit` | `unit` | схемы Pydantic, функции 404/409 (с mock-сессией), настройки и логирование, без БД |
| `tests/integration` | `integration` | все эндпоинты через `TestClient` с настоящей PostgreSQL, коды ответов, фильтры, логи |
| `tests/db` | `db` | ограничения прямо в БД: `UNIQUE`, `CHECK`, `NOT NULL`, внешние ключи, `CASCADE` / `SET NULL` / `RESTRICT`, миграции up/down |
| `tests/e2e` | `e2e` | запускает настоящий сервер Uvicorn и проходит весь сценарий из задания по HTTP, включая перезапуск |

Покрытие кода (`app/`) равно **100%** (строки и ветвления). Порог задан в `pyproject.toml`: если покрытие станет меньше 100%, тесты упадут.

Тестам нужна **отдельная** база в переменной `TEST_DATABASE_URL`. Перед каждым тестом её таблицы очищаются, поэтому рабочую базу указывать нельзя.

Запуск через Docker (ничего устанавливать не нужно, тестовая БД поднимается сама):

```bash
docker compose --profile test run --rm --build tests
docker compose --profile test down
```

Запуск только одного вида тестов:

```bash
docker compose --profile test run --rm --build tests pytest -m unit
docker compose --profile test run --rm --build tests pytest -m e2e
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) запускается при каждом `push` и pull request. В пайплайне три джобы:

1. **Style:** `ruff format --check` и `ruff check` проверяют форматирование и стиль кода.
2. **Static analysis:** `mypy` в строгом режиме (`strict`) проверяет типы.
3. **Tests:** `pytest` с PostgreSQL 16 и проверкой покрытия 100%.

Те же проверки локально:

```bash
pip install -r requirements-dev.txt
ruff format --check . && ruff check .
mypy
pytest --cov
```

## Структура проекта

```text
.
├── app/
│   ├── main.py            # приложение, подключение роутеров, /health
│   ├── config.py          # настройки из окружения (DATABASE_URL)
│   ├── database.py        # engine, сессия, Base
│   ├── logging_config.py  # настройка логов (LOG_LEVEL)
│   ├── models.py          # ORM-модели пяти таблиц
│   ├── schemas.py         # Pydantic-схемы запросов и ответов
│   └── routers/           # users, projects, labels, tasks, comments + общие функции
├── alembic/
│   ├── env.py
│   └── versions/          # миграции
├── tests/                 # unit, integration, db, e2e
├── .github/workflows/ci.yml
├── alembic.ini
├── pyproject.toml         # настройки ruff, mypy, pytest, coverage
├── Dockerfile
├── Dockerfile.test        # образ для запуска тестов
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── requirements.txt
└── requirements-dev.txt   # инструменты для тестов и проверок
```
