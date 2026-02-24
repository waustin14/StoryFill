import re
from typing import Optional

from pydantic import BaseModel


class SlotType(BaseModel):
  name: str
  label: str
  min_length: int
  max_length: int
  quote_in_story: bool = False


SLOT_TYPE_REGISTRY: dict[str, SlotType] = {
  "adjective": SlotType(name="adjective", label="An adjective", min_length=1, max_length=24),
  "name": SlotType(name="name", label="A person", min_length=1, max_length=40),
  "verb": SlotType(name="verb", label="A verb ending in -ing", min_length=1, max_length=30),
  "place": SlotType(name="place", label="A place", min_length=1, max_length=40),
  "sound": SlotType(name="sound", label="A silly sound", min_length=1, max_length=24, quote_in_story=True),
  "noun": SlotType(name="noun", label="A noun", min_length=1, max_length=40),
  "food": SlotType(name="food", label="A type of food", min_length=1, max_length=40),
  "animal": SlotType(name="animal", label="An animal", min_length=1, max_length=40),
  "body_part": SlotType(name="body_part", label="A body part", min_length=1, max_length=40),
  "liquid": SlotType(name="liquid", label="A type of liquid", min_length=1, max_length=40),
  "clothing": SlotType(name="clothing", label="An article of clothing", min_length=1, max_length=40),
  "number": SlotType(name="number", label="A large number", min_length=1, max_length=20),
  "color": SlotType(name="color", label="A color", min_length=1, max_length=24),
  "plural_noun": SlotType(name="plural_noun", label="A plural noun", min_length=1, max_length=40),
}

DEFAULT_SLOT_TYPE = SlotType(name="unknown", label="A word or phrase", min_length=1, max_length=60)


class CustomSlot(BaseModel):
  type: str
  label: Optional[str] = None


def get_slot_type(name: str) -> SlotType:
  return SLOT_TYPE_REGISTRY.get(name, DEFAULT_SLOT_TYPE)


def slot_limits(name: str) -> tuple[int, int]:
  slot_type = get_slot_type(name)
  return (slot_type.min_length, slot_type.max_length)


_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def extract_placeholders(story: str) -> list[str]:
  seen: set[str] = set()
  result: list[str] = []
  for match in _PLACEHOLDER_RE.finditer(story):
    placeholder = match.group(1)
    if placeholder not in seen:
      seen.add(placeholder)
      result.append(placeholder)
  return result


_SUFFIX_RE = re.compile(r"^(.+)_(\d+)$")


def infer_type_from_placeholder(placeholder: str) -> str:
  m = _SUFFIX_RE.match(placeholder)
  if m:
    base = m.group(1)
    if base in SLOT_TYPE_REGISTRY:
      return base
  if placeholder in SLOT_TYPE_REGISTRY:
    return placeholder
  return placeholder


def resolve_slots(
  story: str,
  custom_slots: dict[str, CustomSlot] | None = None,
) -> list[dict[str, str]]:
  """Return a list of {id, label, type} dicts inferred from story placeholders."""
  custom = custom_slots or {}
  placeholders = extract_placeholders(story)
  slots: list[dict[str, str]] = []
  for placeholder in placeholders:
    if placeholder in custom:
      cs = custom[placeholder]
      slot_type = get_slot_type(cs.type)
      label = cs.label if cs.label else slot_type.label
      resolved_type = cs.type
    else:
      resolved_type = infer_type_from_placeholder(placeholder)
      slot_type = get_slot_type(resolved_type)
      label = slot_type.label
    slots.append({"id": placeholder, "label": label, "type": resolved_type})
  return slots
