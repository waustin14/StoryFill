from typing import Optional

from pydantic import BaseModel

from app.db.models import Template as TemplateRow


class TemplateSummary(BaseModel):
  id: str
  title: str
  genre: str
  content_rating: str


class TemplateSlot(BaseModel):
  id: str
  label: str
  type: str


class TemplateDefinition(TemplateSummary):
  slots: list[TemplateSlot]
  story: str
  narration_hints: list[str] = []


# ---------------------------------------------------------------------------
# Authoring format — templates are defined with just a story string and
# optional custom_slots.  Slots are inferred from {placeholders} at load time.
# ---------------------------------------------------------------------------

# Import here (after TemplateSlot is defined) to avoid circular imports.
from app.data.slot_types import CustomSlot, resolve_slots  # noqa: E402


class TemplateAuthoringDefinition(BaseModel):
  id: str
  title: str
  genre: str
  content_rating: str
  story: str
  custom_slots: Optional[dict[str, CustomSlot]] = None
  narration_hints: list[str] = []


def _resolve(authoring: TemplateAuthoringDefinition) -> TemplateDefinition:
  return TemplateDefinition(
    id=authoring.id,
    title=authoring.title,
    genre=authoring.genre,
    content_rating=authoring.content_rating,
    slots=[TemplateSlot(**s) for s in resolve_slots(authoring.story, authoring.custom_slots)],
    story=authoring.story,
    narration_hints=authoring.narration_hints,
  )


_AUTHORING_DEFINITIONS: list[TemplateAuthoringDefinition] = [
  TemplateAuthoringDefinition(
    id="t-forest-mishap",
    title="The Forest Mishap",
    genre="Adventure",
    content_rating="family",
    story=(
      "On a {adjective} morning, {name} was {verb} through the {place} when a {sound} startled a {noun}. "
      "Everyone laughed, then asked for an encore."
    ),
    narration_hints=["Bright and outdoorsy", "Play up the silly sound moment"],
  ),
  TemplateAuthoringDefinition(
    id="t-space-diner",
    title="Midnight at the Space Diner",
    genre="Sci-Fi",
    content_rating="family",
    story=(
      "At the {place} space diner, {name} kept {verb} until a {adjective} {noun} burst in with a {sound}. "
      "The crowd cheered and ordered dessert."
    ),
    narration_hints=["Noir sci-fi vibe", "Pause for the sound effect"],
  ),
  TemplateAuthoringDefinition(
    id="t-castle-caper",
    title="The Castle Caper",
    genre="Fantasy",
    content_rating="family",
    story=(
      "Inside the {adjective} castle, {name} was caught {verb} past the {place} when a {sound} spooked the {noun}. "
      "A royal encore was demanded."
    ),
    narration_hints=["Regal tone with a playful twist"],
  ),
  TemplateAuthoringDefinition(
    id="t-museum-heist",
    title="The Curious Museum Heist",
    genre="Mystery",
    content_rating="family",
    story=(
      "During a {adjective} tour of the {place}, {name} was {verb} when a {sound} echoed over the {noun}. "
      "The guide insisted on an encore."
    ),
    narration_hints=["Whispered suspense", "Emphasize the echo"],
  ),
  TemplateAuthoringDefinition(
    id="t-wild-west",
    title="Sundown in the Wild West",
    genre="Western",
    content_rating="family",
    story=(
      "At the {place} saloon, {name} was {verb} when a {sound} scared a {adjective} herd of {noun}. "
      "The town roared for a repeat."
    ),
    narration_hints=["Dusty western drawl", "Big finish"],
  ),
  TemplateAuthoringDefinition(
    id="t-ocean-odyssey",
    title="The Ocean Odyssey",
    genre="Adventure",
    content_rating="family",
    story=(
      "On the {adjective} deck of the {place}, {name} was {verb} when a {sound} startled the {noun}. "
      "The crew begged for an encore."
    ),
    narration_hints=["Seafaring excitement", "Make the sound splashy"],
  ),
  TemplateAuthoringDefinition(
    id="t-library-lockdown",
    title="The Library Lockdown",
    genre="Mystery",
    content_rating="family",
    story=(
      "Detective {detective} tiptoed into the {adjective} library, clutching a {object}. "
      "A {sound} echoed through the {place}, and suspect {suspect} froze in their tracks."
    ),
    custom_slots={
      "detective": CustomSlot(type="name"),
      "object": CustomSlot(type="noun"),
      "suspect": CustomSlot(type="name"),
    },
    narration_hints=["Quiet suspense", "Let the sound echo"],
  ),
  TemplateAuthoringDefinition(
    id="t-starlight-rescue",
    title="Starlight Rescue",
    genre="Sci-Fi",
    content_rating="family",
    story=(
      "{name} was {verb} across the {adjective} skies of {planet} when the {gadget} blared a {sound}. "
      "The rescue mission had begun."
    ),
    custom_slots={
      "planet": CustomSlot(type="place"),
      "gadget": CustomSlot(type="noun"),
    },
    narration_hints=["Heroic sci-fi tone", "Build urgency on the sound"],
  ),
  TemplateAuthoringDefinition(
    id="t-dragon-parade",
    title="The Dragon Parade",
    genre="Fantasy",
    content_rating="family",
    story=(
      "Hero {hero} led a {adjective} {creature} through {place}, chanting the spell '{spell}'. "
      "At the finish, the {quest} shimmered with magic."
    ),
    custom_slots={
      "hero": CustomSlot(type="name"),
      "creature": CustomSlot(type="noun"),
      "spell": CustomSlot(type="sound"),
      "quest": CustomSlot(type="noun"),
    },
    narration_hints=["Festive fantasy", "Chant the spell"],
  ),
  TemplateAuthoringDefinition(
    id="t-bakery-blizzard",
    title="The Bakery Blizzard",
    genre="Comedy",
    content_rating="family",
    story=(
      "{name} was {verb} in the {place} bakery when a {adjective} {food} caused a {sound}. "
      "Flour flew everywhere and the crowd cheered."
    ),
    narration_hints=["Goofy energy", "Punch the sound effect"],
  ),
  TemplateAuthoringDefinition(
    id="t-jungle-jam",
    title="Jungle Jam Session",
    genre="Adventure",
    content_rating="family",
    story=(
      "In the {place} jungle, {name} started {verb} with a {sound}. "
      "Soon a {adjective} band of {noun} joined the chorus."
    ),
    narration_hints=["Rhythmic, musical cadence", "Make it a jam"],
  ),
  TemplateAuthoringDefinition(
    id="t-turbulence-and-snacks",
    title="Turbulence and Snacks",
    genre="Comedy",
    content_rating="family",
    story=(
      "My vacation flight seemed perfectly ordinary until the pilot introduced himself as Captain {pilot_name} "
      "and announced we would be cruising at an altitude of {large_number} feet. As the plane taxied, "
      "a passenger in row twelve began {verb_1} while gripping their {body_part} with deep concentration. "
      "The flight attendants distributed a single serving of {food_1} paired with a thimble of {liquid} to each row, "
      "explaining that it was essential for cabin balance. Just before takeoff, the intercom let out a {sound_1}, "
      "which no one acknowledged in any way. Midway through the flight we hit {adjective_1} turbulence, "
      "and a startled {animal} somehow appeared in the overhead bin. The passenger next to me {verb_2} "
      "and pulled a {clothing} over their head for protection. The captain came back on with a soft {sound_2} "
      "and calmly assured us this was all part of the {adjective_2} in-flight experience. "
      "We eventually touched down in {place}, where every passenger was handed a complimentary {food_2} "
      "and told to have a {adjective_3} day."
    ),
    custom_slots={
      "pilot_name": CustomSlot(type="name"),
      "large_number": CustomSlot(type="number"),
    },
    narration_hints=[
      "Read with calm confidence, like a seasoned travel narrator.",
      "Let the odd details land by keeping the tone deadpan and serious.",
      "Give each sound effect a brief, dramatic pause before continuing.",
    ],
  ),
]

TEMPLATE_DEFINITIONS: dict[str, TemplateDefinition] = {
  authoring.id: _resolve(authoring) for authoring in _AUTHORING_DEFINITIONS
}

TEMPLATE_SUMMARIES: list[TemplateSummary] = [
  TemplateSummary(
    id=definition.id,
    title=definition.title,
    genre=definition.genre,
    content_rating=definition.content_rating,
  )
  for definition in TEMPLATE_DEFINITIONS.values()
]


def get_template_definition(template_id: str | None) -> TemplateDefinition | None:
  if not template_id:
    return None
  return TEMPLATE_DEFINITIONS.get(template_id)


def default_template_definition() -> TemplateDefinition:
  return next(iter(TEMPLATE_DEFINITIONS.values()))


def _definition_from_row(row: TemplateRow) -> TemplateDefinition:
  definition = row.definition or {}
  slots = definition.get("slots") or []
  return TemplateDefinition(
    id=row.id,
    title=row.title,
    genre=row.genre,
    content_rating=row.content_rating,
    slots=[TemplateSlot(**slot) for slot in slots],
    story=definition.get("story") or "",
    narration_hints=definition.get("narration_hints") or [],
  )


def list_templates_from_db(db) -> list[TemplateSummary]:
  try:
    rows = db.query(TemplateRow).order_by(TemplateRow.title.asc()).all()
  except Exception:
    return TEMPLATE_SUMMARIES
  if not rows:
    return TEMPLATE_SUMMARIES
  return [
    TemplateSummary(id=row.id, title=row.title, genre=row.genre, content_rating=row.content_rating)
    for row in rows
  ]


def get_template_from_db(db, template_id: str) -> TemplateDefinition | None:
  try:
    row = db.query(TemplateRow).filter(TemplateRow.id == template_id).one_or_none()
  except Exception:
    return get_template_definition(template_id)
  if not row:
    return get_template_definition(template_id)
  return _definition_from_row(row)
