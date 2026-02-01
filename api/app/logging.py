import json
import logging
from datetime import datetime, timezone

from app.middleware.request_id import request_id_var


class JsonFormatter(logging.Formatter):
  def format(self, record: logging.LogRecord) -> str:
    payload = {
      "timestamp": datetime.now(timezone.utc).isoformat(),
      "level": record.levelname,
      "message": record.getMessage(),
      "logger": record.name,
      "request_id": request_id_var.get(),
    }
    return json.dumps(payload, default=str)


def configure_logging() -> None:
  handler = logging.StreamHandler()
  handler.setFormatter(JsonFormatter())
  root = logging.getLogger()
  root.setLevel(logging.INFO)
  root.handlers = [handler]
