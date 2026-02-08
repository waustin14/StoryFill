import { describe, expect, it } from "vitest"

import { renderStory } from "@/lib/story-renderer"

const STORY = "On a {adjective} morning, {name} was {verb} through the {place} when a {sound} startled a {noun}. Everyone laughed, then asked for an encore."

const SLOTS = [
  { id: "adjective", label: "An adjective", type: "adjective" },
  { id: "name", label: "A famous name", type: "name" },
  { id: "verb", label: "A verb ending in -ing", type: "verb" },
  { id: "place", label: "A place", type: "place" },
  { id: "sound", label: "A silly sound", type: "sound" },
  { id: "noun", label: "A plural noun", type: "noun" },
]

describe("renderStory", () => {
  it("fills slots and quotes sounds", () => {
    const result = renderStory(STORY, SLOTS, [
      { slotId: "adjective", value: "brave" },
      { slotId: "name", value: "Sam" },
      { slotId: "verb", value: "running" },
      { slotId: "place", value: "forest" },
      { slotId: "sound", value: "boom" },
      { slotId: "noun", value: "squirrels" },
    ])
    expect(result).toContain("\"boom\"")
    expect(result).toContain("Sam")
  })

  it("quotes sound slots by type, not id", () => {
    const story = "The intercom let out a {sound_1} and then a {sound_2}."
    const slots = [
      { id: "sound_1", label: "A silly sound", type: "sound" },
      { id: "sound_2", label: "A silly sound", type: "sound" },
    ]
    const result = renderStory(story, slots, [
      { slotId: "sound_1", value: "whoosh" },
      { slotId: "sound_2", value: "zap" },
    ])
    expect(result).toContain("\"whoosh\"")
    expect(result).toContain("\"zap\"")
  })
})
