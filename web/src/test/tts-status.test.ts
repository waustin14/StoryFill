import { describe, expect, it } from "vitest"

import { ttsStatusLabel } from "@/lib/tts-status"

describe("ttsStatusLabel", () => {
  it("returns friendly labels for key statuses", () => {
    expect(ttsStatusLabel("blocked", false, "blocked")).toBe("blocked")
    expect(ttsStatusLabel("error", false, null)).toBe("Narration failed. Try again.")
    expect(ttsStatusLabel("generating", false, null)).toBe("Generating narration...")
    expect(ttsStatusLabel("from_cache", true, null)).toBe("Narration ready (cached).")
    expect(ttsStatusLabel("ready", false, null)).toBe("Narration ready.")
    expect(ttsStatusLabel("idle", false, null)).toBe("Narration hasn't been requested yet.")
  })
})
