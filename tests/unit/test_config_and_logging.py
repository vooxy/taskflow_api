"""Модульные тесты настроек, логирования и вспомогательных функций БД."""

import logging
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from app import database
from app.config import Settings
from app.logging_config import setup_logging
from tests.helpers import UNREACHABLE_DB_URL


class TestSettings:
    def test_log_level_default_is_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert Settings(_env_file=None, database_url="sqlite://").log_level == "INFO"

    def test_log_level_from_env_is_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "debug")
        assert Settings(_env_file=None, database_url="sqlite://").log_level == "DEBUG"

    @pytest.mark.parametrize("value", ["verbose", 10])
    def test_invalid_log_level(self, value: object) -> None:
        with pytest.raises(ValidationError):
            Settings.model_validate({"database_url": "sqlite://", "log_level": value})

    def test_database_url_is_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


@pytest.fixture
def restore_app_logger() -> Iterator[None]:
    app_logger = logging.getLogger("app")
    level, handlers = app_logger.level, app_logger.handlers[:]
    yield
    app_logger.setLevel(level)
    app_logger.handlers = handlers


class TestSetupLogging:
    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_sets_level(self, level: str, restore_app_logger: None) -> None:
        setup_logging(level)
        assert logging.getLogger("app").level == getattr(logging, level)

    def test_level_filters_messages(
        self, restore_app_logger: None, caplog: pytest.LogCaptureFixture
    ) -> None:
        setup_logging("WARNING")
        logger = logging.getLogger("app.test")
        logger.info("hidden")
        logger.warning("shown")
        assert [r.getMessage() for r in caplog.records] == ["shown"]


class TestDatabaseHelpers:
    def test_get_db_closes_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = MagicMock()
        monkeypatch.setattr(database, "SessionLocal", lambda: session)
        generator = database.get_db()
        assert next(generator) is session
        session.close.assert_not_called()
        with pytest.raises(StopIteration):
            next(generator)
        session.close.assert_called_once()

    def test_check_database_false_when_unreachable(self) -> None:
        assert database.check_database(create_engine(UNREACHABLE_DB_URL)) is False
