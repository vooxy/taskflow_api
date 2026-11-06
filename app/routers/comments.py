from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routers.common import PathId, commit_or_409, get_or_404

router = APIRouter()


@router.get("", response_model=list[schemas.CommentRead])
def list_comments(
    task_id: int | None = Query(default=None, gt=0, le=2_147_483_647),
    db: Session = Depends(get_db),
):
    """Список комментариев. Фильтр: `?task_id=1` (необязателен)."""
    statement = select(models.Comment)
    if task_id is not None:
        statement = statement.where(models.Comment.task_id == task_id)
    return db.scalars(statement.order_by(models.Comment.id)).all()


@router.get("/{comment_id}", response_model=schemas.CommentRead)
def get_comment(comment_id: PathId, db: Session = Depends(get_db)):
    return get_or_404(db, models.Comment, comment_id)


@router.post("", response_model=schemas.CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(payload: schemas.CommentCreate, db: Session = Depends(get_db)):
    comment = models.Comment(**payload.model_dump())
    db.add(comment)
    commit_or_409(db)
    db.refresh(comment)
    return comment


@router.patch("/{comment_id}", response_model=schemas.CommentRead)
def update_comment(
    comment_id: PathId, payload: schemas.CommentUpdate, db: Session = Depends(get_db)
):
    comment = get_or_404(db, models.Comment, comment_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(comment, field, value)
    commit_or_409(db)
    db.refresh(comment)
    return comment


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: PathId, db: Session = Depends(get_db)) -> None:
    comment = get_or_404(db, models.Comment, comment_id)
    db.delete(comment)
    commit_or_409(db)
