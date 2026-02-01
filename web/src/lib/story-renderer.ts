import { getTemplateDefinition } from "@/lib/template-definitions"

type PromptValue = {
  slotId?: string
  type?: string
  value?: string
}

export function renderStory(templateId: string | null | undefined, prompts: PromptValue[]): string {
  const template = getTemplateDefinition(templateId)
  const values = new Map<string, string>()
  for (const prompt of prompts) {
    if (!prompt.value) continue
    const key = prompt.slotId ?? prompt.type
    if (!key) continue
    if (!values.has(key)) {
      values.set(key, prompt.value.trim())
    }
  }

  let rendered = template.story
  for (const slot of template.slots) {
    const raw = values.get(slot.id) ?? "something"
    let value = raw
    if (slot.id === "sound" && raw && !(raw.startsWith("\"") && raw.endsWith("\""))) {
      value = `"${raw}"`
    }
    rendered = rendered.replace(`{${slot.id}}`, value)
  }

  return rendered
}
