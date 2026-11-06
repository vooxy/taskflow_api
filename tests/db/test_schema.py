"""Тесты БД: ограничения и правила внешних ключей проверяются в самой PostgreSQL,
минуя API (через SQLAlchemy-сессию), а также проверяются миграции Alembic."""

from collections.abc import Callable
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app import models
from app.database import engine

APP_TABLES = {"users", "projects", "labels", "tasks", "comments"}


@pytest.fixture
def add(db_session: Session) -> Callable[..., Any]:
    def _add(obj: Any) -> Any:
        db_session.add(obj)
        db_session.commit()
        db_session.refresh(obj)
        return obj

    return _add


@pytest.fixture
def graph(add: Callable[..., Any]) -> dict[str, Any]:
    """Пользователь, метка, проект, задача и комментарий, связанные между собой."""
    user = add(models.User(email="u@example.com", display_name="U"))
    label = add(models.Label(name="bug"))
    project = add(models.Project(name="P"))
    task = add(
        models.Task(project_id=project.id, assignee_id=user.id, label_id=label.id, title="T")
    )
    comment = add(models.Comment(task_id=task.id, author_id=user.id, body="hi"))
    return {"user": user, "label": label, "project": project, "task": task, "comment": comment}


def assert_rejected(db_session: Session, obj: Any) -> None:
    db_session.add(obj)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


class TestSchemaStructure:
    def test_exactly_five_app_tables(self, migrated: None) -> None:
        tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
        assert tables == APP_TABLES

    @pytest.mark.parametrize(
        ("table", "column", "ondelete"),
        [
            ("tasks", "project_id", "CASCADE"),
            ("tasks", "assignee_id", "SET NULL"),
            ("tasks", "label_id", "SET NULL"),
            ("comments", "task_id", "CASCADE"),
            ("comments", "author_id", "RESTRICT"),
        ],
    )
    def test_foreign_key_rules(
        self, migrated: None, table: str, column: str, ondelete: str
    ) -> None:
        fks = inspect(engine).get_foreign_keys(table)
        fk = next(fk for fk in fks if fk["constrained_columns"] == [column])
        assert fk["options"]["ondelete"] == ondelete


class TestDefaults:
    def test_server_defaults(self, graph: dict[str, Any]) -> None:
        assert graph["user"].role == "operator"
        assert graph["label"].color == "#6b7280"
        assert graph["task"].status == "open"
        assert graph["task"].priority == "medium"
        for obj in graph.values():
            if hasattr(obj, "created_at"):
                assert obj.created_at is not None
                assert obj.created_at.tzinfo is not None

    def test_updated_at_changes_on_update(self, db_session: Session, graph: dict[str, Any]) -> None:
        task = graph["task"]
        before = task.updated_at
        task.status = "done"
        db_session.commit()
        db_session.refresh(task)
        assert task.updated_at > before


class TestConstraints:
    def test_unique_email(self, db_session: Session, graph: dict[str, Any]) -> None:
        assert_rejected(db_session, models.User(email="u@example.com", display_name="X"))

    def test_unique_label_name(self, db_session: Session, graph: dict[str, Any]) -> None:
        assert_rejected(db_session, models.Label(name="bug"))

    @pytest.mark.parametrize(
        "factory",
        [
            lambda g: models.User(email="x@example.com", display_name="X", role="boss"),
            lambda g: models.Label(name="x", color="red"),
            lambda g: models.Task(project_id=g["project"].id, title="T", status="closed"),
            lambda g: models.Task(project_id=g["project"].id, title="T", priority="urgent"),
            lambda g: models.Comment(task_id=g["task"].id, author_id=g["user"].id, body="   "),
        ],
        ids=["role", "color", "status", "priority", "blank-body"],
    )
    def test_check_constraints(
        self, db_session: Session, graph: dict[str, Any], factory: Callable[..., Any]
    ) -> None:
        assert_rejected(db_session, factory(graph))

    @pytest.mark.parametrize(
        "factory",
        [
            lambda g: models.Task(project_id=999, title="T"),
            lambda g: models.Task(project_id=g["project"].id, assignee_id=999, title="T"),
            lambda g: models.Task(project_id=g["project"].id, label_id=999, title="T"),
            lambda g: models.Comment(task_id=999, author_id=g["user"].id, body="x"),
            lambda g: models.Comment(task_id=g["task"].id, author_id=999, body="x"),
        ],
        ids=["project", "assignee", "label", "task", "author"],
    )
    def test_invalid_foreign_keys(
        self, db_session: Session, graph: dict[str, Any], factory: Callable[..., Any]
    ) -> None:
        assert_rejected(db_session, factory(graph))

    @pytest.mark.parametrize(
        "factory",
        [
            lambda g: models.User(email="x@example.com"),
            lambda g: models.Project(),
            lambda g: models.Task(project_id=g["project"].id),
            lambda g: models.Comment(task_id=g["task"].id, author_id=g["user"].id),
        ],
        ids=["user", "project", "task", "comment"],
    )
    def test_not_null(
        self, db_session: Session, graph: dict[str, Any], factory: Callable[..., Any]
    ) -> None:
        assert_rejected(db_session, factory(graph))


class TestDeleteRules:
    def test_project_delete_cascades_to_tasks_and_comments(
        self, db_session: Session, graph: dict[str, Any]
    ) -> None:
        db_session.delete(graph["project"])
        db_session.commit()
        assert db_session.scalars(select(models.Task)).all() == []
        assert db_session.scalars(select(models.Comment)).all() == []
        assert db_session.get(models.User, graph["user"].id) is not None

    def test_task_delete_cascades_to_comments(
        self, db_session: Session, graph: dict[str, Any]
    ) -> None:
        db_session.delete(graph["task"])
        db_session.commit()
        assert db_session.scalars(select(models.Comment)).all() == []

    def test_label_delete_sets_null(self, db_session: Session, graph: dict[str, Any]) -> None:
        task_id = graph["task"].id
        db_session.delete(graph["label"])
        db_session.commit()
        db_session.expire_all()
        task = db_session.get(models.Task, task_id)
        assert task is not None and task.label_id is None

    def test_user_with_comments_cannot_be_deleted(
        self, db_session: Session, graph: dict[str, Any]
    ) -> None:
        db_session.delete(graph["user"])
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_assignee_delete_sets_null(self, db_session: Session, graph: dict[str, Any]) -> None:
        db_session.delete(graph["comment"])
        db_session.delete(graph["user"])
        db_session.commit()
        db_session.expire_all()
        task = db_session.get(models.Task, graph["task"].id)
        assert task is not None and task.assignee_id is None


class TestMigrations:
    def test_downgrade_and_upgrade(self, migrated: None, alembic_config: Config) -> None:
        command.downgrade(alembic_config, "base")
        assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set()

        command.upgrade(alembic_config, "head")
        assert set(inspect(engine).get_table_names()) - {"alembic_version"} == APP_TABLES

        # повторный upgrade ничего не делает и не падает
        command.upgrade(alembic_config, "head")

    def test_models_match_migrations(self, migrated: None, alembic_config: Config) -> None:
        # alembic check падает, если модели и миграции расходятся
        command.check(alembic_config)
