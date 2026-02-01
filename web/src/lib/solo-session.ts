import { getTemplateDefinition } from "@/lib/template-definitions"

export type PromptAssignment = {
  id: string
  slotId: string
  label: string
  type: string
  value?: string
}

export type SoloSession = {
  roomId: string
  roundId: string
  templateId: string | null
  prompts: PromptAssignment[]
  createdAt: string
}

const STORAGE_KEY = "storyfill.soloSession"

function createId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID()}`
  }
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 10000)}`
}

export function createSoloSession(templateId: string | null): SoloSession {
  const template = getTemplateDefinition(templateId)
  const prompts = template.slots.map((slot) => ({
    id: createId("prompt"),
    slotId: slot.id,
    label: slot.label,
    type: slot.type,
  }))
  return {
    roomId: createId("room"),
    roundId: createId("round"),
    templateId,
    prompts,
    createdAt: new Date().toISOString(),
  }
}

export function saveSoloSession(session: SoloSession) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function loadSoloSession(): SoloSession | null {
  if (typeof window === "undefined") return null
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as SoloSession
  } catch {
    return null
  }
}

export function restartSoloRound(session: SoloSession): SoloSession {
  const template = getTemplateDefinition(session.templateId)
  const prompts = template.slots.map((slot) => ({
    id: createId("prompt"),
    slotId: slot.id,
    label: slot.label,
    type: slot.type,
  }))
  return {
    ...session,
    roundId: createId("round"),
    prompts,
    createdAt: new Date().toISOString(),
  }
}

export function clearSoloSession() {
  if (typeof window === "undefined") return
  window.localStorage.removeItem(STORAGE_KEY)
}
