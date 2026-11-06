# TaskFlow API

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

## Структура проекта

```text
.
├── app/
│   ├── main.py            # приложение, подключение роутеров, /health
│   ├── config.py          # настройки из окружения (DATABASE_URL)
│   ├── database.py        # engine, сессия, Base
│   ├── models.py          # ORM-модели пяти таблиц
│   ├── schemas.py         # Pydantic-схемы запросов и ответов
│   └── routers/           # users, projects, labels, tasks, comments + общие функции
├── alembic/
│   ├── env.py
│   └── versions/          # миграции
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
└── requirements.txt
```
