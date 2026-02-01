from fastapi import APIRouter, HTTPException

from app.data.templates import (
  TEMPLATE_SUMMARIES,
  TemplateDefinition,
  TemplateSummary,
  get_template_definition,
)

router = APIRouter(prefix="/v1", tags=["templates"])


@router.get("/templates", response_model=list[TemplateSummary])
def list_templates():
  return TEMPLATE_SUMMARIES


@router.get("/templates/{template_id}", response_model=TemplateDefinition)
def get_template(template_id: str):
  definition = get_template_definition(template_id)
  if not definition:
    raise HTTPException(status_code=404, detail="Template not found.")
  return definition
