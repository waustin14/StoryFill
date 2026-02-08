from __future__ import annotations

import re
from typing import Optional

# Minimal-but-useful moderation for a family-safe MVP.
# This is intentionally simple and self-contained so it can later be swapped for a
# dedicated profanity library or hosted moderation API without touching callers.

# NOTE: Keep these lowercase and ASCII.
BLOCKED_TERMS: set[str] = {
  # Sexual content
  "porn",
  "porno",
  "pussy",
  "dick",
  "cock",
  "penis",
  "vagina",
  "boob",
  "boobs",
  "tits",
  "tit",
  "cum",
  "sex",
  "sexy",
  "horny",
  "rape",
  # Slurs / hate
  "nazi",
  "hitler",
  # Violence / terror (coarse filter; can be refined)
  "terrorist",
  # General profanity
  "fuck",
  "fucking",
  "shit",
  "bitch",
  "cunt",
  "asshole",
  "bastard",
  "motherfucker",
}

_LEET_MAP = str.maketrans(
  {
    "@": "a",
    "$": "s",
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "8": "b",
    "9": "g",
    "!": "i",
    "+": "t",
  }
)


def _normalize(text: str) -> str:
  lowered = text.lower().translate(_LEET_MAP)
  # Turn punctuation into spaces so we can detect inserted separators (e.g. "f.u.c.k").
  lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
  # Collapse long repeated characters ("fuuuuuck" -> "fuuck") to reduce trivial bypasses.
  lowered = re.sub(r"(.)\\1{2,}", r"\\1\\1", lowered)
  return lowered


def moderation_block_reason(text: str) -> Optional[str]:
  """Return a friendly user-facing block reason, or None if allowed."""
  if not text or not text.strip():
    return None

  normalized = _normalize(text)

  # Check for whole-word matches and also spaced-out letter matches (e.g. "f u c k").
  for term in BLOCKED_TERMS:
    # Whole word in normalized text.
    if re.search(rf"\\b{re.escape(term)}\\b", normalized):
      return "That response includes language we can't accept. Please try a different word or phrase."
    # Spaced-out letters / separators turned into spaces by normalization.
    spaced = r"\b" + r"\s*".join(map(re.escape, term)) + r"\b"
    if re.search(spaced, normalized):
      return "That response includes language we can't accept. Please try a different word or phrase."

  return None
