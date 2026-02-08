from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.data.templates import (
  TemplateDefinition,
  TemplateSummary,
  get_template_from_db,
  list_templates_from_db,
)
from app.db.session import get_db

router = APIRouter(prefix="/v1", tags=["templates"])


@router.get("/templates", response_model=list[TemplateSummary])
def list_templates(db: Session = Depends(get_db)):
  return list_templates_from_db(db)


@router.get("/templates/{template_id}", response_model=TemplateDefinition)
def get_template(template_id: str, db: Session = Depends(get_db)):
  definition = get_template_from_db(db, template_id)
  if not definition:
    raise HTTPException(status_code=404, detail="Template not found.")
  return definition
