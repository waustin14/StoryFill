import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.moderation import moderation_block_reason
from app.core.rate_limit import check_rate_limit
from app.data.polish import polish_story

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["solo"])


class SoloPolishRequest(BaseModel):
    story: str
    session_id: str | None = None
    round_id: str | None = None


class SoloPolishResponse(BaseModel):
    polished_story: str
    moderation_blocked: bool
    block_message: str | None = None


@router.post("/solo/polish", response_model=SoloPolishResponse)
def solo_polish_handler(payload: SoloPolishRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    result = check_rate_limit(f"ip:{client_ip}:solo_polish", limit=10, window_seconds=300)
    if not result.allowed:
        headers = {"Retry-After": str(result.retry_after)} if result.retry_after else None
        raise HTTPException(
            status_code=429,
            detail="Polish requests are rate limited. Please wait a moment and try again.",
            headers=headers,
        )

    block_reason = moderation_block_reason(payload.story)
    if block_reason:
        return SoloPolishResponse(
            polished_story=payload.story,
            moderation_blocked=True,
            block_message=block_reason,
        )

    polished = polish_story(payload.story)
    return SoloPolishResponse(
        polished_story=polished,
        moderation_blocked=False,
    )
