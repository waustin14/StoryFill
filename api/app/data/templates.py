from typing import Optional

from pydantic import BaseModel

from app.db.models import Template as TemplateRow


class TemplateSummary(BaseModel):
  id: str
  title: str
  genre: str
  content_rating: str
  description: str


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
  description: str
  story: str
  custom_slots: Optional[dict[str, CustomSlot]] = None
  narration_hints: list[str] = []


def _resolve(authoring: TemplateAuthoringDefinition) -> TemplateDefinition:
  return TemplateDefinition(
    id=authoring.id,
    title=authoring.title,
    genre=authoring.genre,
    content_rating=authoring.content_rating,
    description=authoring.description,
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
    description="A silly woodland adventure where unexpected noises lead to unexpected encores.",
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
    description="A noir-flavored late-night scene at an intergalactic greasy spoon.",
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
    description="Sneak through a royal castle where every wrong turn ends in royal applause.",
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
    description="A whisper-quiet museum tour goes sideways when strange echoes take over.",
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
    description="A dusty saloon showdown where the biggest threat is a spooked herd.",
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
    description="High-seas hijinks aboard a ship where the crew demands an encore.",
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
    description="A detective, a suspect, and a mysterious object in the quietest room imaginable.",
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
    description="A heroic dash across alien skies when a gadget sounds the alarm.",
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
    description="Lead a magical creature through town chanting spells until something shimmers.",
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
    description="A flour-covered catastrophe in the kitchen that leaves the crowd cheering.",
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
    description="Deep in the jungle, one sound kicks off an impromptu animal jam session.",
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
    description="A perfectly ordinary flight that is anything but, from takeoff to complimentary snack.",
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
  TemplateAuthoringDefinition(
    id="t-electric-jam",
    title="The Electric Jam",
    genre="Comedy",
    content_rating="family",
    description="A rock band bio where every member is wilder than the last.",
    story=(
      "The band has been playing {adjective_1}-style music together for {number} years. "
      "Their lead singer, {singer}, plays a mean keyboard and likes to {verb_1} on the microphone. "
      "The guitarist shakes the tambourine and wails as one of the most {adjective_2} singers around. "
      "The bassist rocks out on the {adjective_3} bass and plays the vibes with lots of {noun_1} and soul. "
      "The saxophonist is the {adjective_4} one, always wearing a {adjective_5} fedora over their {body_part}. "
      "The trumpet player shakes their {color} hair like a wild {noun_2}. "
      "And of course, the drummer is the most {adjective_6} of them all — "
      "loving drums, {plural_noun_1}, and rock and roll, "
      "bashing the kit like they want to {verb_2} it! "
      "The band travels the world in their psychedelic {noun_3}. "
      "And when they get to your {adjective_7} town, it's time to let your hair down, "
      "put on your {plural_noun_2}, and shake your groove {noun_4} all night long!"
    ),
    custom_slots={
      "singer": CustomSlot(type="name"),
    },
    narration_hints=[
      "Read like an enthusiastic rock documentary narrator.",
      "Build energy with each band member introduction.",
      "Go big on the finale.",
    ],
  ),
  TemplateAuthoringDefinition(
    id="t-critics-corner",
    title="The Critics' Corner",
    genre="Comedy",
    content_rating="family",
    description="Two grumpy theater critics trade insults about the worst show they've ever seen.",
    story=(
      '"Why do these stories all have {number} words missing?" asked one critic. '
      '"Beats me," replied the other. "But remember, we\'re talking about the {adjective_1} theater. '
      'When has anything here ever made sense?" '
      '"Good point. If you\'re looking for sense, don\'t try to get it from this show!" '
      '"This performance is so hard to watch, it makes {adjective_2} paint drying look like '
      'a {adjective_3} blockbuster." '
      '"This script is so {adjective_4}, it makes a {noun_1} of knock-knock jokes look like '
      'great literature!" '
      '"Why do they call this {adjective_5} thing entertainment?" '
      '"More like {noun_2}!" '
      '"I\'d rather eat live {plural_noun_1} than sit through this again!" '
      '"There\'s one good thing I can say about this {adjective_6} show..." '
      '"What\'s that?" '
      '"It makes a great {noun_3}!" '
      '"Ha! Say, let\'s go eat some {food}... I\'m starved!"'
    ),
    narration_hints=[
      "Read as a back-and-forth dialogue between two grumpy old men.",
      "Deliver each insult with deadpan timing.",
      "End on a cheerful note when food is mentioned.",
    ],
  ),
  TemplateAuthoringDefinition(
    id="t-chaotic-chef",
    title="The Chaotic Chef",
    genre="Comedy",
    content_rating="family",
    description="A legendary, incomprehensible chef whose kitchen disasters are somehow delicious.",
    story=(
      "Have you ever eaten exploding {verb_1} shrimp? How about a soufflé that's so fluffy "
      "it goes {noun_1} into the air? Or a banana split that comes with its own dancing "
      "{plural_noun_1}? If you have, then you've probably enjoyed some delicacies made by "
      "the world's most chaotic chef. From {adjective_1} crème brûlée to the bushy "
      "{plural_noun_2} beneath his nose, this chef is easy to recognize and impossible to "
      "understand. But whenever he's {verb_2} in the kitchen, you can tell he knows what "
      "he's doing — even if no one else can figure it out. Why is he always {verb_3} "
      "everywhere and putting {plural_noun_3} in the skillet? The chef might have some "
      "{adjective_2} ideas, like making doughnuts by poking {food} holes in {adjective_3} "
      "muffins, but he is always happy to share his culinary {plural_noun_4} with anybody "
      "who wants to watch. And he's not afraid to sacrifice his own {noun_2} for his recipes, "
      "even with sauce so {adjective_4}, it blows his hat off his {body_part}!"
    ),
    narration_hints=[
      "Read like an awestruck food documentary narrator.",
      "Lean into the absurdity with genuine admiration.",
      "Speed up during the chaotic kitchen moments.",
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
    description=definition.description,
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
    description=row.description or "",
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
    TemplateSummary(
      id=row.id,
      title=row.title,
      genre=row.genre,
      content_rating=row.content_rating,
      description=row.description or "",
    )
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
