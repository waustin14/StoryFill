export type TemplateSlot = {
  id: string
  label: string
  type: string
}

export type TemplateDefinition = {
  id: string
  title: string
  genre: string
  contentRating: string
  slots: TemplateSlot[]
  story: string
}

const BASE_SLOTS: TemplateSlot[] = [
  { id: "adjective", label: "An adjective", type: "adjective" },
  { id: "name", label: "A famous name", type: "name" },
  { id: "verb", label: "A verb ending in -ing", type: "verb" },
  { id: "place", label: "A place", type: "place" },
  { id: "sound", label: "A silly sound", type: "sound" },
  { id: "noun", label: "A plural noun", type: "noun" },
]

export const TEMPLATE_DEFINITIONS: Record<string, TemplateDefinition> = {
  "t-forest-mishap": {
    id: "t-forest-mishap",
    title: "The Forest Mishap",
    genre: "Adventure",
    contentRating: "family",
    slots: BASE_SLOTS,
    story:
      "On a {adjective} morning, {name} was {verb} through the {place} when a {sound} startled a {noun}. Everyone laughed, then asked for an encore.",
  },
  "t-space-diner": {
    id: "t-space-diner",
    title: "Midnight at the Space Diner",
    genre: "Sci-Fi",
    contentRating: "family",
    slots: BASE_SLOTS,
    story:
      "At the {place} space diner, {name} kept {verb} until a {adjective} {noun} burst in with a {sound}. The crowd cheered and ordered dessert.",
  },
  "t-castle-caper": {
    id: "t-castle-caper",
    title: "The Castle Caper",
    genre: "Fantasy",
    contentRating: "family",
    slots: BASE_SLOTS,
    story:
      "Inside the {adjective} castle, {name} was caught {verb} past the {place} when a {sound} spooked the {noun}. A royal encore was demanded.",
  },
  "t-museum-heist": {
    id: "t-museum-heist",
    title: "The Curious Museum Heist",
    genre: "Mystery",
    contentRating: "family",
    slots: BASE_SLOTS,
    story:
      "During a {adjective} tour of the {place}, {name} was {verb} when a {sound} echoed over the {noun}. The guide insisted on an encore.",
  },
  "t-wild-west": {
    id: "t-wild-west",
    title: "Sundown in the Wild West",
    genre: "Western",
    contentRating: "family",
    slots: BASE_SLOTS,
    story:
      "At the {place} saloon, {name} was {verb} when a {sound} scared a {adjective} herd of {noun}. The town roared for a repeat.",
  },
  "t-ocean-odyssey": {
    id: "t-ocean-odyssey",
    title: "The Ocean Odyssey",
    genre: "Adventure",
    contentRating: "family",
    slots: BASE_SLOTS,
    story:
      "On the {adjective} deck of the {place}, {name} was {verb} when a {sound} startled the {noun}. The crew begged for an encore.",
  },
}

export function getTemplateDefinition(templateId: string | null | undefined): TemplateDefinition {
  if (templateId && TEMPLATE_DEFINITIONS[templateId]) {
    return TEMPLATE_DEFINITIONS[templateId]
  }
  const first = Object.values(TEMPLATE_DEFINITIONS)[0]
  return first
}
