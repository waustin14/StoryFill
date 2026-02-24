from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import WEB_ORIGINS
from app.logging import configure_logging
from app.middleware.request_id import request_id_middleware
from app.otel import init_tracing
from app.db.session import SessionLocal
from app.db.models import Template as TemplateRow
from app.db.seed_templates import seed_templates
from app.routes.health import router as health_router
from app.routes.rooms import router as rooms_router
from app.routes.templates import router as templates_router
from app.routes.solo import router as solo_router
from app.routes.tts import router as tts_router
from app.routes.ws import router as ws_router

configure_logging()

def _seed_templates_if_possible() -> None:
  # Best-effort seed so local dev has templates after `infra/scripts/migrate.sh`.
  try:
    db = SessionLocal()
    try:
      count = db.query(TemplateRow).count()
      if count == 0:
        seed_templates(db)
    finally:
      db.close()
  except Exception:
    return


@asynccontextmanager
async def lifespan(_app: FastAPI):
  _seed_templates_if_possible()
  yield


app = FastAPI(title="StoryFill API", lifespan=lifespan)
app.add_middleware(
  CORSMiddleware,
  allow_origins=WEB_ORIGINS,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
app.middleware("http")(request_id_middleware)
init_tracing(app)
app.include_router(templates_router)
app.include_router(rooms_router)
app.include_router(solo_router)
app.include_router(tts_router)
app.include_router(ws_router)
app.include_router(health_router)
