import type { TemplateSlot } from "@/lib/template-definitions"

type PromptValue = {
  slotId?: string
  type?: string
  value?: string
}

export function renderStory(story: string, slots: TemplateSlot[], prompts: PromptValue[]): string {
  const values = new Map<string, string>()
  for (const prompt of prompts) {
    if (!prompt.value) continue
    const key = prompt.slotId ?? prompt.type
    if (!key) continue
    if (!values.has(key)) {
      values.set(key, prompt.value.trim())
    }
  }

  let rendered = story
  for (const slot of slots) {
    const raw = values.get(slot.id) ?? "something"
    let value = raw
    if (slot.type === "sound" && raw && !(raw.startsWith("\"") && raw.endsWith("\""))) {
      value = `"${raw}"`
    }
    rendered = rendered.replaceAll(`{${slot.id}}`, value)
  }

  return rendered
}
