"""Модульные тесты Pydantic-схем: валидация без БД и без HTTP."""

import pytest
from pydantic import ValidationError

from app import schemas


class TestUserSchemas:
    def test_create_defaults_role_to_operator(self) -> None:
        user = schemas.UserCreate(email="a@example.com", display_name="A")
        assert user.role == "operator"

    @pytest.mark.parametrize(
        "payload",
        [
            {"email": "not-an-email", "display_name": "A"},
            {"email": "a@example.com", "display_name": ""},
            {"email": "a@example.com", "display_name": "A", "role": "boss"},
            {"email": "a@example.com", "display_name": "A", "id": 1},
            {"email": "a@example.com", "display_name": "A", "created_at": "2026-01-01"},
            {"display_name": "A"},
        ],
    )
    def test_create_rejects_invalid(self, payload: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            schemas.UserCreate.model_validate(payload)

    def test_update_accepts_partial_payload(self) -> None:
        update = schemas.UserUpdate.model_validate({"role": "admin"})
        assert update.model_dump(exclude_unset=True) == {"role": "admin"}

    def test_update_rejects_null_for_required_field(self) -> None:
        with pytest.raises(ValidationError, match="cannot be null"):
            schemas.UserUpdate.model_validate({"email": None})


class TestProjectSchemas:
    def test_update_allows_null_description(self) -> None:
        update = schemas.ProjectUpdate.model_validate({"description": None})
        assert update.model_dump(exclude_unset=True) == {"description": None}

    def test_update_rejects_null_name(self) -> None:
        with pytest.raises(ValidationError):
            schemas.ProjectUpdate.model_validate({"name": None})

    def test_name_length_limit(self) -> None:
        with pytest.raises(ValidationError):
            schemas.ProjectCreate(name="x" * 201)


class TestLabelSchemas:
    def test_default_color(self) -> None:
        assert schemas.LabelCreate(name="bug").color == "#6b7280"

    @pytest.mark.parametrize("color", ["#ABCDEF", "#00ff00"])
    def test_valid_colors(self, color: str) -> None:
        assert schemas.LabelCreate(name="bug", color=color).color == color

    @pytest.mark.parametrize("color", ["red", "#12345", "#1234567", "123456", "#GGGGGG"])
    def test_invalid_colors(self, color: str) -> None:
        with pytest.raises(ValidationError):
            schemas.LabelCreate(name="bug", color=color)


class TestTaskSchemas:
    def test_create_defaults(self) -> None:
        task = schemas.TaskCreate(project_id=1, title="T")
        assert (task.status, task.priority, task.assignee_id, task.label_id) == (
            "open",
            "medium",
            None,
            None,
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"project_id": 1, "title": "T", "status": "closed"},
            {"project_id": 1, "title": "T", "priority": "urgent"},
            {"project_id": 0, "title": "T"},
            {"project_id": 2_147_483_648, "title": "T"},
            {"project_id": 1, "title": ""},
            {"title": "T"},
        ],
    )
    def test_create_rejects_invalid(self, payload: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            schemas.TaskCreate.model_validate(payload)

    def test_update_allows_null_for_nullable_fields(self) -> None:
        update = schemas.TaskUpdate.model_validate(
            {"assignee_id": None, "label_id": None, "description": None}
        )
        assert update.model_dump(exclude_unset=True) == {
            "assignee_id": None,
            "label_id": None,
            "description": None,
        }

    @pytest.mark.parametrize("field", ["project_id", "title", "status", "priority"])
    def test_update_rejects_null_for_required_fields(self, field: str) -> None:
        with pytest.raises(ValidationError):
            schemas.TaskUpdate.model_validate({field: None})


class TestCommentSchemas:
    @pytest.mark.parametrize("body", ["", "   ", "\n\t"])
    def test_create_rejects_blank_body(self, body: str) -> None:
        with pytest.raises(ValidationError):
            schemas.CommentCreate(task_id=1, author_id=1, body=body)

    def test_update_rejects_blank_body(self) -> None:
        with pytest.raises(ValidationError):
            schemas.CommentUpdate(body="  ")

    def test_update_cannot_change_task(self) -> None:
        with pytest.raises(ValidationError):
            schemas.CommentUpdate.model_validate({"task_id": 2})

    def test_valid_comment(self) -> None:
        assert schemas.CommentCreate(task_id=1, author_id=1, body=" ok ").body == " ok "
