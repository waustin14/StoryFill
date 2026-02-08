const WORKING_STATUSES = new Set(["requesting", "queued", "generating"])

export function ttsStatusLabel(status: string, fromCache: boolean, errorMessage?: string | null) {
  if (status === "blocked") return errorMessage || "Narration is disabled for this round."
  if (status === "error") return errorMessage || "Narration failed. Try again."
  if (WORKING_STATUSES.has(status)) return "Generating narration..."
  if (status === "ready" || status === "from_cache") {
    return fromCache ? "Narration ready (cached)." : "Narration ready."
  }
  return "Narration hasn't been requested yet."
}
