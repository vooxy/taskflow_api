"""Общие функции для всех роутеров: поиск записи (404) и сохранение с обработкой ошибок БД (409)."""

from typing import Annotated, TypeVar

from fastapi import HTTPException, Path, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)

# id в URL: положительное число в пределах integer PostgreSQL
PathId = Annotated[int, Path(gt=0, le=2_147_483_647)]

# коды ошибок PostgreSQL (SQLSTATE)
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"


def get_or_404(db: Session, model: type[ModelT], record_id: int) -> ModelT:
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    return record


def commit_or_409(db: Session) -> None:
    """Сохраняет транзакцию. Нарушение уникальности или внешнего ключа -> 409.

    Текст ошибки БД клиенту не отдаётся: он раскрывает структуру таблиц.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        code = getattr(exc.orig, "pgcode", None)
        if code == UNIQUE_VIOLATION:
            detail = "Record with this unique value already exists"
        elif code == FOREIGN_KEY_VIOLATION:
            detail = (
                "Referenced record does not exist, "
                "or this record is still referenced by other records"
            )
        else:
            detail = "Data conflicts with database constraints"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
