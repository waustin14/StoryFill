import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import ModeSelectClient from "@/app/mode/mode-select-client"

const pushMock = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}))

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

describe("ModeSelectClient", () => {
  beforeEach(() => {
    pushMock.mockClear()
    window.localStorage.clear()
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_TEMPLATE),
      })
    ))
  })

  it("warns when no template is selected", () => {
    render(<ModeSelectClient />)
    expect(screen.getByRole("status")).toHaveTextContent("No template selected yet.")
  })

  it("creates a solo session and navigates to prompting", async () => {
    window.localStorage.setItem("storyfill.templateId", "t-forest-mishap")
    render(<ModeSelectClient />)

    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: /solo/i }))

    await waitFor(() => {
      expect(window.localStorage.getItem("storyfill.soloSession")).toBeTruthy()
      expect(pushMock).toHaveBeenCalledWith("/prompting")
    })
  })

  it("navigates to room for multiplayer", async () => {
    render(<ModeSelectClient />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: /multiplayer/i }))
    expect(pushMock).toHaveBeenCalledWith("/room")
  })

  it("supports keyboard focus for mode buttons", async () => {
    render(<ModeSelectClient />)
    const user = userEvent.setup()
    await user.tab()
    expect(screen.getByRole("button", { name: /solo/i })).toHaveFocus()
  })
})
