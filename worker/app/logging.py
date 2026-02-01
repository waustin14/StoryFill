import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
  def format(self, record: logging.LogRecord) -> str:
    payload = {
      "timestamp": datetime.now(timezone.utc).isoformat(),
      "level": record.levelname,
      "message": record.getMessage(),
      "logger": record.name
    }
    return json.dumps(payload, default=str)


def configure_logging() -> None:
  handler = logging.StreamHandler()
  handler.setFormatter(JsonFormatter())
  root = logging.getLogger()
  root.setLevel(logging.INFO)
  root.handlers = [handler]
