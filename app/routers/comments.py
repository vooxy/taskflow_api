import logging
from collections.abc import Sequence

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routers.common import PathId, commit_or_409, get_or_404

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=list[schemas.CommentRead])
def list_comments(
    task_id: int | None = Query(default=None, gt=0, le=2_147_483_647),
    db: Session = Depends(get_db),
) -> Sequence[models.Comment]:
    """Список комментариев. Фильтр: `?task_id=1` (необязателен)."""
    logger.debug("List comments: task_id=%s", task_id)
    statement = select(models.Comment)
    if task_id is not None:
        statement = statement.where(models.Comment.task_id == task_id)
    return db.scalars(statement.order_by(models.Comment.id)).all()


@router.get("/{comment_id}", response_model=schemas.CommentRead)
def get_comment(comment_id: PathId, db: Session = Depends(get_db)) -> models.Comment:
    return get_or_404(db, models.Comment, comment_id)


@router.post("", response_model=schemas.CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(payload: schemas.CommentCreate, db: Session = Depends(get_db)) -> models.Comment:
    comment = models.Comment(**payload.model_dump())
    db.add(comment)
    commit_or_409(db)
    db.refresh(comment)
    logger.info("Comment %s created", comment.id)
    return comment


@router.patch("/{comment_id}", response_model=schemas.CommentRead)
def update_comment(
    comment_id: PathId, payload: schemas.CommentUpdate, db: Session = Depends(get_db)
) -> models.Comment:
    comment = get_or_404(db, models.Comment, comment_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(comment, field, value)
    commit_or_409(db)
    db.refresh(comment)
    logger.info("Comment %s updated", comment.id)
    return comment


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: PathId, db: Session = Depends(get_db)) -> None:
    comment = get_or_404(db, models.Comment, comment_id)
    db.delete(comment)
    commit_or_409(db)
    logger.info("Comment %s deleted", comment_id)
