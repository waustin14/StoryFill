from pydantic import BaseModel


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


BASE_SLOTS: list[TemplateSlot] = [
  TemplateSlot(id="adjective", label="An adjective", type="adjective"),
  TemplateSlot(id="name", label="A famous name", type="name"),
  TemplateSlot(id="verb", label="A verb ending in -ing", type="verb"),
  TemplateSlot(id="place", label="A place", type="place"),
  TemplateSlot(id="sound", label="A silly sound", type="sound"),
  TemplateSlot(id="noun", label="A plural noun", type="noun"),
]

TEMPLATE_DEFINITIONS: dict[str, TemplateDefinition] = {
  "t-forest-mishap": TemplateDefinition(
    id="t-forest-mishap",
    title="The Forest Mishap",
    genre="Adventure",
    content_rating="family",
    slots=BASE_SLOTS,
    story=(
      "On a {adjective} morning, {name} was {verb} through the {place} when a {sound} startled a {noun}. "
      "Everyone laughed, then asked for an encore."
    ),
  ),
  "t-space-diner": TemplateDefinition(
    id="t-space-diner",
    title="Midnight at the Space Diner",
    genre="Sci-Fi",
    content_rating="family",
    slots=BASE_SLOTS,
    story=(
      "At the {place} space diner, {name} kept {verb} until a {adjective} {noun} burst in with a {sound}. "
      "The crowd cheered and ordered dessert."
    ),
  ),
  "t-castle-caper": TemplateDefinition(
    id="t-castle-caper",
    title="The Castle Caper",
    genre="Fantasy",
    content_rating="family",
    slots=BASE_SLOTS,
    story=(
      "Inside the {adjective} castle, {name} was caught {verb} past the {place} when a {sound} spooked the {noun}. "
      "A royal encore was demanded."
    ),
  ),
  "t-museum-heist": TemplateDefinition(
    id="t-museum-heist",
    title="The Curious Museum Heist",
    genre="Mystery",
    content_rating="family",
    slots=BASE_SLOTS,
    story=(
      "During a {adjective} tour of the {place}, {name} was {verb} when a {sound} echoed over the {noun}. "
      "The guide insisted on an encore."
    ),
  ),
  "t-wild-west": TemplateDefinition(
    id="t-wild-west",
    title="Sundown in the Wild West",
    genre="Western",
    content_rating="family",
    slots=BASE_SLOTS,
    story=(
      "At the {place} saloon, {name} was {verb} when a {sound} scared a {adjective} herd of {noun}. "
      "The town roared for a repeat."
    ),
  ),
  "t-ocean-odyssey": TemplateDefinition(
    id="t-ocean-odyssey",
    title="The Ocean Odyssey",
    genre="Adventure",
    content_rating="family",
    slots=BASE_SLOTS,
    story=(
      "On the {adjective} deck of the {place}, {name} was {verb} when a {sound} startled the {noun}. "
      "The crew begged for an encore."
    ),
  ),
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
