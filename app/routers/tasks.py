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


@router.get("", response_model=list[schemas.TaskRead])
def list_tasks(
    project_id: int | None = Query(default=None, gt=0, le=2_147_483_647),
    status: schemas.TaskStatus | None = None,
    db: Session = Depends(get_db),
) -> Sequence[models.Task]:
    """Список задач. Фильтры: `?project_id=1&status=open` (оба необязательны)."""
    logger.debug("List tasks: project_id=%s status=%s", project_id, status)
    statement = select(models.Task)
    if project_id is not None:
        statement = statement.where(models.Task.project_id == project_id)
    if status is not None:
        statement = statement.where(models.Task.status == status)
    return db.scalars(statement.order_by(models.Task.id)).all()


@router.get("/{task_id}", response_model=schemas.TaskRead)
def get_task(task_id: PathId, db: Session = Depends(get_db)) -> models.Task:
    return get_or_404(db, models.Task, task_id)


@router.post("", response_model=schemas.TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)) -> models.Task:
    # Несуществующий project_id / assignee_id / label_id -> БД отклонит -> 409
    task = models.Task(**payload.model_dump())
    db.add(task)
    commit_or_409(db)
    db.refresh(task)
    logger.info("Task %s created", task.id)
    return task


@router.patch("/{task_id}", response_model=schemas.TaskRead)
def update_task(
    task_id: PathId, payload: schemas.TaskUpdate, db: Session = Depends(get_db)
) -> models.Task:
    task = get_or_404(db, models.Task, task_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    commit_or_409(db)  # updated_at обновится автоматически (onupdate=now())
    db.refresh(task)
    logger.info("Task %s updated", task.id)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: PathId, db: Session = Depends(get_db)) -> None:
    # Комментарии задачи удалит БД (ON DELETE CASCADE)
    task = get_or_404(db, models.Task, task_id)
    db.delete(task)
    commit_or_409(db)
    logger.info("Task %s deleted", task_id)
