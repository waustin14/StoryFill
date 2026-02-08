import { beforeEach, describe, expect, it, vi } from "vitest"

import { clearSoloSession, createSoloSession, loadSoloSession, restartSoloRound, saveSoloSession } from "@/lib/solo-session"

const MOCK_TEMPLATE = {
  id: "t-forest-mishap",
  title: "The Forest Mishap",
  genre: "Adventure",
  content_rating: "family",
  story: "On a {adjective} morning, {name} was {verb} through the {place} when a {sound} startled a {noun}.",
  slots: [
    { id: "adjective", label: "An adjective", type: "adjective" },
    { id: "name", label: "A famous name", type: "name" },
    { id: "verb", label: "A verb ending in -ing", type: "verb" },
    { id: "place", label: "A place", type: "place" },
    { id: "sound", label: "A silly sound", type: "sound" },
    { id: "noun", label: "A plural noun", type: "noun" },
  ],
}

describe("solo session", () => {
  beforeEach(() => {
    window.localStorage.clear()
    let counter = 0
    vi.stubGlobal("crypto", { randomUUID: () => `mocked-${counter++}` })
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_TEMPLATE),
      })
    ))
  })

  it("creates and stores a session", async () => {
    const session = await createSoloSession("t-forest-mishap")
    saveSoloSession(session)
    const loaded = loadSoloSession()
    expect(loaded).not.toBeNull()
    expect(loaded?.templateId).toBe("t-forest-mishap")
    expect(loaded?.story).toBe(MOCK_TEMPLATE.story)
    expect(loaded?.slots).toEqual(MOCK_TEMPLATE.slots)
    expect(loaded?.prompts.length).toBeGreaterThan(0)
  })

  it("restarts a solo round with a new round id", async () => {
    const session = await createSoloSession("t-forest-mishap")
    const restarted = restartSoloRound(session)
    expect(restarted.roundId).not.toBe(session.roundId)
    expect(restarted.prompts.length).toBe(session.prompts.length)
  })

  it("clears a stored session", async () => {
    const session = await createSoloSession("t-forest-mishap")
    saveSoloSession(session)
    clearSoloSession()
    expect(loadSoloSession()).toBeNull()
  })

  it("returns null for stale sessions without story or slots", () => {
    window.localStorage.setItem(
      "storyfill.soloSession",
      JSON.stringify({ roomId: "r", roundId: "rd", templateId: "t", prompts: [], createdAt: "" })
    )
    expect(loadSoloSession()).toBeNull()
  })
})
