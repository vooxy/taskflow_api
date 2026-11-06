"""Интеграционные тесты приложения: /health, /docs, обработка сбоев и логирование."""

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import database
from app.database import get_db
from app.main import app
from tests.helpers import UNREACHABLE_DB_URL


@pytest.fixture
def debug_logs(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.DEBUG, logger="app")
    return caplog


def messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_docs_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for resource in ["users", "projects", "labels", "tasks", "comments"]:
        assert f"/v1/{resource}" in paths
        assert f"/v1/{resource}/{{{resource[:-1]}_id}}" in paths


def test_health_returns_503_and_logs_error_when_db_down(
    client: TestClient, debug_logs: pytest.LogCaptureFixture
) -> None:
    def broken_db() -> Iterator[Session]:
        session = Session(bind=create_engine(UNREACHABLE_DB_URL))
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = broken_db
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert any("503" in m for m in messages(debug_logs, logging.ERROR))


def test_unhandled_error_returns_500_and_logs_error(
    clean_db: None, debug_logs: pytest.LogCaptureFixture
) -> None:
    def exploding_db() -> Iterator[Session]:
        raise RuntimeError("boom")
        yield  # недостижимо: нужен только чтобы функция была генератором

    app.dependency_overrides[get_db] = exploding_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get("/v1/projects")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "boom" not in response.text
    assert any("Unhandled error" in m for m in messages(debug_logs, logging.ERROR))


def test_startup_logs_critical_when_db_unavailable(
    monkeypatch: pytest.MonkeyPatch, debug_logs: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(database, "check_database", lambda _engine: False)
    with TestClient(app):
        pass
    assert any("Database is unavailable" in m for m in messages(debug_logs, logging.CRITICAL))


def test_all_log_levels_in_normal_flow(
    client: TestClient, debug_logs: pytest.LogCaptureFixture
) -> None:
    client.post("/v1/projects", json={"name": "P"})
    client.get("/v1/tasks?status=open")
    client.get("/v1/comments?task_id=1")
    client.get("/v1/projects/999")
    client.post("/v1/projects", json={})

    debug = messages(debug_logs, logging.DEBUG)
    info = messages(debug_logs, logging.INFO)
    warning = messages(debug_logs, logging.WARNING)

    assert "DB session opened" in debug
    assert "DB session closed" in debug
    assert any(m.startswith("Request started: GET /v1/tasks") for m in debug)
    assert "List tasks: project_id=None status=open" in debug
    assert "List comments: task_id=1" in debug
    assert "Project 1 created" in info
    assert any(m.startswith("POST /v1/projects -> 201") for m in info)
    assert any("404: Project not found" in m for m in warning)
    assert any("422" in m for m in warning)


def test_log_level_hides_debug(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="app")
    client.get("/v1/projects")
    assert caplog.records == []


def test_startup_and_shutdown_are_logged(
    clean_db: None, debug_logs: pytest.LogCaptureFixture
) -> None:
    with TestClient(app):
        pass
    info = messages(debug_logs, logging.INFO)
    assert any(m.startswith("Starting TaskFlow API") for m in info)
    assert "TaskFlow API stopped" in info
