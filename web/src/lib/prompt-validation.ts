const DEFAULT_LIMITS = { min: 1, max: 60 }
const SLOT_LIMITS: Record<string, { min: number; max: number }> = {
  adjective: { min: 1, max: 24 },
  name: { min: 1, max: 40 },
  verb: { min: 1, max: 30 },
  place: { min: 1, max: 40 },
  sound: { min: 1, max: 24 },
  noun: { min: 1, max: 40 },
}
const BLOCKED_MESSAGE =
  "That response includes language we can't accept. Please try a different word or phrase."
const BLOCKED_TERMS = new Set([
  "porn",
  "porno",
  "pussy",
  "dick",
  "cock",
  "penis",
  "vagina",
  "boob",
  "boobs",
  "tits",
  "tit",
  "cum",
  "sex",
  "sexy",
  "horny",
  "rape",
  "nazi",
  "hitler",
  "terrorist",
  "fuck",
  "fucking",
  "shit",
  "bitch",
  "cunt",
  "asshole",
  "bastard",
  "motherfucker",
])
const LEET_MAP: Record<string, string> = {
  "@": "a",
  $: "s",
  "0": "o",
  "1": "i",
  "3": "e",
  "4": "a",
  "5": "s",
  "7": "t",
  "8": "b",
  "9": "g",
  "!": "i",
  "+": "t",
}

export function promptLimits(slotType?: string | null) {
  if (!slotType) return DEFAULT_LIMITS
  const key = slotType.toLowerCase()
  return SLOT_LIMITS[key] ?? DEFAULT_LIMITS
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function normalizePrompt(value: string) {
  const lowered = value
    .toLowerCase()
    .split("")
    .map((char) => LEET_MAP[char] ?? char)
    .join("")
  const stripped = lowered.replace(/[^a-z0-9\s]/g, " ")
  return stripped.replace(/(.)\1{2,}/g, "$1$1")
}

function moderationBlockReason(value: string) {
  if (!value || !value.trim()) return null
  const normalized = normalizePrompt(value)
  for (const term of BLOCKED_TERMS) {
    const whole = new RegExp(`\\b${escapeRegex(term)}\\b`)
    if (whole.test(normalized)) return BLOCKED_MESSAGE
    const spaced = new RegExp(`\\b${term.split("").map(escapeRegex).join("\\s*")}\\b`)
    if (spaced.test(normalized)) return BLOCKED_MESSAGE
  }
  return null
}

export function getPromptIssue(value: string, slotType?: string | null) {
  if (!value || !value.trim()) {
    return "Please add a response before submitting."
  }
  const trimmed = value.trim()
  for (const char of trimmed) {
    const code = char.charCodeAt(0)
    if (code < 32 || code > 126) {
      return (
        "That response includes characters we can't read yet. " +
        "Use letters, numbers, and common punctuation only, and remove emoji or control characters."
      )
    }
  }
  const { min, max } = promptLimits(slotType)
  if (trimmed.length < min) {
    return "That response is too short. Please add a little more detail."
  }
  if (trimmed.length > max) {
    return `That response is too long. Please keep it under ${max} characters.`
  }
  const blockReason = moderationBlockReason(trimmed)
  if (blockReason) return blockReason
  return null
}

export function isReadable(value: string, slotType?: string | null) {
  return !getPromptIssue(value, slotType)
}
