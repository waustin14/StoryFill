from app.data.slot_types import (
  CustomSlot,
  DEFAULT_SLOT_TYPE,
  SLOT_TYPE_REGISTRY,
  extract_placeholders,
  get_slot_type,
  infer_type_from_placeholder,
  resolve_slots,
  slot_limits,
)


def test_extract_placeholders_ordering_and_dedup():
  story = "The {adjective} {noun} met a {adjective} {verb} at {place}"
  result = extract_placeholders(story)
  assert result == ["adjective", "noun", "verb", "place"]


def test_extract_placeholders_numbered_suffixes():
  story = "{sound_1} then {sound_2} then {adjective}"
  result = extract_placeholders(story)
  assert result == ["sound_1", "sound_2", "adjective"]


def test_infer_type_strips_numeric_suffix():
  assert infer_type_from_placeholder("adjective_2") == "adjective"
  assert infer_type_from_placeholder("sound_1") == "sound"
  assert infer_type_from_placeholder("verb_3") == "verb"
  assert infer_type_from_placeholder("food_1") == "food"


def test_infer_type_preserves_compound_names():
  assert infer_type_from_placeholder("body_part") == "body_part"


def test_infer_type_exact_match():
  assert infer_type_from_placeholder("adjective") == "adjective"
  assert infer_type_from_placeholder("noun") == "noun"


def test_infer_type_unknown_passes_through():
  assert infer_type_from_placeholder("detective") == "detective"
  assert infer_type_from_placeholder("gadget") == "gadget"


def test_resolve_slots_registry_only():
  story = "A {adjective} {noun} in the {place}"
  slots = resolve_slots(story)
  assert len(slots) == 3
  assert slots[0]["id"] == "adjective"
  assert slots[0]["type"] == "adjective"
  assert slots[0]["label"] == "An adjective"
  assert slots[1]["id"] == "noun"
  assert slots[1]["type"] == "noun"
  assert slots[1]["label"] == "A noun"
  assert slots[2]["id"] == "place"
  assert slots[2]["type"] == "place"
  assert slots[2]["label"] == "A place"


def test_resolve_slots_with_custom_slots():
  story = "Detective {detective} found the {object}"
  custom = {
    "detective": CustomSlot(type="name"),
    "object": CustomSlot(type="noun"),
  }
  slots = resolve_slots(story, custom)
  assert len(slots) == 2
  assert slots[0]["id"] == "detective"
  assert slots[0]["type"] == "name"
  assert slots[0]["label"] == "A person"
  assert slots[1]["id"] == "object"
  assert slots[1]["type"] == "noun"
  assert slots[1]["label"] == "A noun"


def test_resolve_slots_custom_label_override():
  story = "Cast the spell '{spell}'"
  custom = {"spell": CustomSlot(type="sound", label="A magic word")}
  slots = resolve_slots(story, custom)
  assert len(slots) == 1
  assert slots[0]["id"] == "spell"
  assert slots[0]["type"] == "sound"
  assert slots[0]["label"] == "A magic word"


def test_resolve_slots_with_numbered_suffixes():
  story = "{adjective_1} {adjective_2} {sound_1}"
  slots = resolve_slots(story)
  assert len(slots) == 3
  assert slots[0]["id"] == "adjective_1"
  assert slots[0]["type"] == "adjective"
  assert slots[0]["label"] == "An adjective"
  assert slots[1]["id"] == "adjective_2"
  assert slots[1]["type"] == "adjective"
  assert slots[2]["id"] == "sound_1"
  assert slots[2]["type"] == "sound"


def test_slot_limits_known_type():
  assert slot_limits("adjective") == (1, 24)
  assert slot_limits("name") == (1, 40)
  assert slot_limits("sound") == (1, 24)
  assert slot_limits("number") == (1, 20)


def test_slot_limits_unknown_type_returns_defaults():
  assert slot_limits("detective") == (DEFAULT_SLOT_TYPE.min_length, DEFAULT_SLOT_TYPE.max_length)
  assert slot_limits("detective") == (1, 60)


def test_sound_type_has_quote_in_story():
  sound = SLOT_TYPE_REGISTRY["sound"]
  assert sound.quote_in_story is True


def test_non_sound_types_no_quote():
  for name, slot_type in SLOT_TYPE_REGISTRY.items():
    if name != "sound":
      assert slot_type.quote_in_story is False, f"{name} should not quote in story"


def test_get_slot_type_returns_default_for_unknown():
  result = get_slot_type("nonexistent")
  assert result == DEFAULT_SLOT_TYPE
  assert result.label == "A word or phrase"
