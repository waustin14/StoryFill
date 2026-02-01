import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="unknown")


async def request_id_middleware(request: Request, call_next: Callable) -> Response:
  incoming = request.headers.get("x-request-id")
  request_id = incoming or str(uuid.uuid4())
  request_id_var.set(request_id)
  response = await call_next(request)
  response.headers["x-request-id"] = request_id
  return response
