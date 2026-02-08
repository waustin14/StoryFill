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
