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


@router.get("", response_model=list[schemas.ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> Sequence[models.Project]:
    return db.scalars(select(models.Project).order_by(models.Project.id)).all()


@router.get("/{project_id}", response_model=schemas.ProjectRead)
def get_project(project_id: PathId, db: Session = Depends(get_db)) -> models.Project:
    return get_or_404(db, models.Project, project_id)


@router.post("", response_model=schemas.ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)) -> models.Project:
    project = models.Project(**payload.model_dump())
    db.add(project)
    commit_or_409(db)
    db.refresh(project)
    logger.info("Project %s created", project.id)
    return project


@router.patch("/{project_id}", response_model=schemas.ProjectRead)
def update_project(
    project_id: PathId, payload: schemas.ProjectUpdate, db: Session = Depends(get_db)
) -> models.Project:
    project = get_or_404(db, models.Project, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    commit_or_409(db)
    db.refresh(project)
    logger.info("Project %s updated", project.id)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: PathId, db: Session = Depends(get_db)) -> None:
    # Задачи проекта и их комментарии удалит сама БД (ON DELETE CASCADE)
    project = get_or_404(db, models.Project, project_id)
    db.delete(project)
    commit_or_409(db)
    logger.info("Project %s deleted", project_id)
