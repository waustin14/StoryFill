from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import WEB_ORIGINS
from app.logging import configure_logging
from app.middleware.request_id import request_id_middleware
from app.otel import init_tracing
from app.routes.rooms import router as rooms_router
from app.routes.templates import router as templates_router
from app.routes.tts import router as tts_router

configure_logging()

app = FastAPI(title="StoryFill API")
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
app.include_router(tts_router)


@app.get("/health")
def health_check():
  return {"status": "ok"}
