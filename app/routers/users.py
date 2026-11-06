import logging
from collections.abc import Sequence

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routers.common import PathId, commit_or_409, get_or_404

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=list[schemas.UserRead])
def list_users(db: Session = Depends(get_db)) -> Sequence[models.User]:
    return db.scalars(select(models.User).order_by(models.User.id)).all()


@router.get("/{user_id}", response_model=schemas.UserRead)
def get_user(user_id: PathId, db: Session = Depends(get_db)) -> models.User:
    return get_or_404(db, models.User, user_id)


@router.post("", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)) -> models.User:
    user = models.User(**payload.model_dump())
    db.add(user)
    commit_or_409(db)
    db.refresh(user)
    logger.info("User %s created", user.id)
    return user


@router.patch("/{user_id}", response_model=schemas.UserRead)
def update_user(
    user_id: PathId, payload: schemas.UserUpdate, db: Session = Depends(get_db)
) -> models.User:
    user = get_or_404(db, models.User, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    commit_or_409(db)
    db.refresh(user)
    logger.info("User %s updated", user.id)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: PathId, db: Session = Depends(get_db)) -> None:
    # Если у пользователя есть комментарии, БД (RESTRICT) запретит удаление -> 409
    user = get_or_404(db, models.User, user_id)
    db.delete(user)
    commit_or_409(db)
    logger.info("User %s deleted", user_id)
