"""Модульные тесты общих функций роутеров: сессия БД подменяется заглушкой (mock)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app import models
from app.routers.common import commit_or_409, get_or_404


def integrity_error(pgcode: str | None) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, SimpleNamespace(pgcode=pgcode))


class TestGetOr404:
    def test_returns_record(self) -> None:
        record = models.Project(id=1, name="P")
        db = MagicMock()
        db.get.return_value = record
        assert get_or_404(db, models.Project, 1) is record
        db.get.assert_called_once_with(models.Project, 1)

    def test_raises_404_with_model_name(self) -> None:
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            get_or_404(db, models.Task, 7)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Task not found"


class TestCommitOr409:
    def test_commits(self) -> None:
        db = MagicMock()
        commit_or_409(db)
        db.commit.assert_called_once()
        db.rollback.assert_not_called()

    @pytest.mark.parametrize(
        ("pgcode", "expected"),
        [
            ("23505", "already exists"),
            ("23503", "Referenced record does not exist"),
            ("23514", "conflicts with database constraints"),
            (None, "conflicts with database constraints"),
        ],
    )
    def test_integrity_error_becomes_409(self, pgcode: str | None, expected: str) -> None:
        db = MagicMock()
        db.commit.side_effect = integrity_error(pgcode)
        with pytest.raises(HTTPException) as exc_info:
            commit_or_409(db)
        assert exc_info.value.status_code == 409
        assert expected in exc_info.value.detail
        db.rollback.assert_called_once()

    def test_detail_does_not_leak_sql(self) -> None:
        db = MagicMock()
        db.commit.side_effect = integrity_error("23505")
        with pytest.raises(HTTPException) as exc_info:
            commit_or_409(db)
        assert "INSERT" not in exc_info.value.detail
