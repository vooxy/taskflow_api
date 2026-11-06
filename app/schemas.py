"""Pydantic-схемы: HTTP-контракт API.

*Create — тело POST, *Update — тело PATCH (все поля необязательны), *Read — ответ.
extra="forbid": служебные поля (id, created_at, ...) от клиента не принимаются -> 422.
В *Update поле можно не передавать, но явный null разрешён только для полей,
которые в БД могут быть NULL (nullable_fields); для остальных -> 422.
"""

from datetime import datetime
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Role = Literal["operator", "admin"]
TaskStatus = Literal["open", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high"]

# id в PostgreSQL — integer (до 2 147 483 647)
Id = Annotated[int, Field(gt=0, le=2_147_483_647)]
Color = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UpdateModel(InputModel):
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_null_for_required(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in self.nullable_fields:
                raise ValueError(f"Field '{name}' cannot be null")
        return self


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _not_blank(value: str | None) -> str | None:
    if value is not None and not value.strip():
        raise ValueError("body must not be empty")
    return value


# ---------- users ----------
class UserCreate(InputModel):
    email: EmailStr = Field(max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    role: Role = "operator"


class UserUpdate(UpdateModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: Role | None = None


class UserRead(ReadModel):
    id: int
    email: str
    display_name: str
    role: Role
    created_at: datetime


# ---------- projects ----------
class ProjectCreate(InputModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectUpdate(UpdateModel):
    nullable_fields = frozenset({"description"})

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ProjectRead(ReadModel):
    id: int
    name: str
    description: str | None
    created_at: datetime


# ---------- labels ----------
class LabelCreate(InputModel):
    name: str = Field(min_length=1, max_length=64)
    color: Color = "#6b7280"


class LabelUpdate(UpdateModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: Color | None = None


class LabelRead(ReadModel):
    id: int
    name: str
    color: str


# ---------- tasks ----------
class TaskCreate(InputModel):
    project_id: Id
    assignee_id: Id | None = None
    label_id: Id | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus = "open"
    priority: TaskPriority = "medium"


class TaskUpdate(UpdateModel):
    nullable_fields = frozenset({"assignee_id", "label_id", "description"})

    project_id: Id | None = None
    assignee_id: Id | None = None
    label_id: Id | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None


class TaskRead(ReadModel):
    id: int
    project_id: int
    assignee_id: int | None
    label_id: int | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime


# ---------- comments ----------
class CommentCreate(InputModel):
    task_id: Id
    author_id: Id
    body: str = Field(min_length=1)

    _check_body = field_validator("body")(_not_blank)


class CommentUpdate(UpdateModel):
    body: str | None = Field(default=None, min_length=1)

    _check_body = field_validator("body")(_not_blank)


class CommentRead(ReadModel):
    id: int
    task_id: int
    author_id: int
    body: str
    created_at: datetime
