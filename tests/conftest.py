"""Общие фикстуры.

Тесты работают с ОТДЕЛЬНОЙ тестовой базой из переменной TEST_DATABASE_URL:
перед каждым тестом её таблицы очищаются, поэтому рабочую базу использовать нельзя.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "Set TEST_DATABASE_URL to a separate test database, e.g. "
        "postgresql+psycopg2://taskflow:taskflow@localhost:5433/taskflow_test"
    )
# Приложение читает DATABASE_URL при импорте — подменяем его до импорта app
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import created  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TABLES = "comments, tasks, labels, projects, users"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Маркер ставится по папке: tests/unit -> unit, tests/db -> db и т.д."""
    for item in items:
        folder = Path(str(item.path)).parent.name
        if folder in {"unit", "integration", "db", "e2e"}:
            item.add_marker(getattr(pytest.mark, folder))


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return Config(str(ROOT / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated(alembic_config: Config) -> None:
    """Схема тестовой БД создаётся миграциями — так же, как в рабочей."""
    command.upgrade(alembic_config, "head")


@pytest.fixture
def clean_db(migrated: None) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db_session(clean_db: None) -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(clean_db: None) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------- фабрики записей через API ----------


@pytest.fixture
def user(client: TestClient) -> dict[str, Any]:
    return created(
        client.post("/v1/users", json={"email": "karim@example.com", "display_name": "Karim"})
    )


@pytest.fixture
def project(client: TestClient) -> dict[str, Any]:
    return created(client.post("/v1/projects", json={"name": "Backend course"}))


@pytest.fixture
def label(client: TestClient) -> dict[str, Any]:
    return created(client.post("/v1/labels", json={"name": "bug", "color": "#ef4444"}))


@pytest.fixture
def task(
    client: TestClient,
    project: dict[str, Any],
    user: dict[str, Any],
    label: dict[str, Any],
) -> dict[str, Any]:
    return created(
        client.post(
            "/v1/tasks",
            json={
                "project_id": project["id"],
                "assignee_id": user["id"],
                "label_id": label["id"],
                "title": "Write CRUD",
            },
        )
    )


@pytest.fixture
def comment(client: TestClient, task: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    return created(
        client.post(
            "/v1/comments",
            json={"task_id": task["id"], "author_id": user["id"], "body": "Started"},
        )
    )
