import logging
import os

import httpx

from app.core.config import POLISH_ENABLED, POLISH_MODEL, POLISH_TIMEOUT

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a grammar proofreader. Fix only grammar issues: subject/verb agreement, "
    "pluralization, and articles (a/an/the). Do not change word choices, meaning, "
    "or creative content. Return only the corrected text with no commentary."
)


def polish_story(story: str) -> str:
    if not POLISH_ENABLED:
        return story

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return story

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
    max_tokens = max(64, int(len(story) * 1.5 / 4))

    try:
        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)
    except Exception:
        tracer = None

    def _call() -> str:
        with httpx.Client(timeout=POLISH_TIMEOUT) as client:
            resp = client.post(
                f"{base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": POLISH_MODEL,
                    "temperature": 0,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": story},
                    ],
                },
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"]
            return result.strip()

    try:
        if tracer:
            with tracer.start_as_current_span("polish.llm_call") as span:
                span.set_attribute("polish.model", POLISH_MODEL)
                polished = _call()
                return polished
        else:
            return _call()
    except Exception:
        logger.warning("polish_story failed, returning original", exc_info=True)
        return story
