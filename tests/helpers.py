"""Вспомогательные константы и функции для тестов."""

from typing import Any

# Адрес, по которому гарантированно нет PostgreSQL (порт 1) — для проверки сбоев БД
UNREACHABLE_DB_URL = "postgresql+psycopg2://nobody:nothing@127.0.0.1:1/nothing"


def created(response: Any) -> dict[str, Any]:
    """Проверяет ответ 201 и возвращает тело."""
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data
