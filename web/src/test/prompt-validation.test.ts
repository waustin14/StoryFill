import { describe, expect, it } from "vitest"

import { getPromptIssue, isReadable } from "@/lib/prompt-validation"

describe("prompt validation", () => {
  it("rejects empty input", () => {
    expect(getPromptIssue("", "noun")).toContain("Please add a response")
  })

  it("rejects non-ascii characters", () => {
    expect(getPromptIssue("hello 👋", "noun")).toContain("characters we can't read yet")
  })

  it("rejects too-long responses", () => {
    const longValue = "a".repeat(41)
    expect(getPromptIssue(longValue, "noun")).toContain("too long")
  })

  it("rejects blocked language", () => {
    expect(getPromptIssue("f u c k", "noun")).toContain("language we can't accept")
  })

  it("accepts valid responses", () => {
    expect(getPromptIssue("brave", "adjective")).toBeNull()
    expect(isReadable("brave", "adjective")).toBe(true)
  })
})
