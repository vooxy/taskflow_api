from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routers.common import PathId, commit_or_409, get_or_404

router = APIRouter()


@router.get("", response_model=list[schemas.LabelRead])
def list_labels(db: Session = Depends(get_db)):
    return db.scalars(select(models.Label).order_by(models.Label.id)).all()


@router.get("/{label_id}", response_model=schemas.LabelRead)
def get_label(label_id: PathId, db: Session = Depends(get_db)):
    return get_or_404(db, models.Label, label_id)


@router.post("", response_model=schemas.LabelRead, status_code=status.HTTP_201_CREATED)
def create_label(payload: schemas.LabelCreate, db: Session = Depends(get_db)):
    label = models.Label(**payload.model_dump())
    db.add(label)
    commit_or_409(db)
    db.refresh(label)
    return label


@router.patch("/{label_id}", response_model=schemas.LabelRead)
def update_label(
    label_id: PathId, payload: schemas.LabelUpdate, db: Session = Depends(get_db)
):
    label = get_or_404(db, models.Label, label_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(label, field, value)
    commit_or_409(db)
    db.refresh(label)
    return label


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(label_id: PathId, db: Session = Depends(get_db)) -> None:
    # В задачах с этой меткой label_id станет NULL (ON DELETE SET NULL)
    label = get_or_404(db, models.Label, label_id)
    db.delete(label)
    commit_or_409(db)
