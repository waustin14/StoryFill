import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import TemplateSelectClient from "@/app/templates/template-select-client"

const pushMock = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => new URLSearchParams(),
}))

describe("TemplateSelectClient", () => {
  beforeEach(() => {
    pushMock.mockClear()
    window.localStorage.clear()
    vi.unstubAllGlobals()
  })

  it("loads templates and allows selection", async () => {
    const templates = [
      { id: "t-forest-mishap", title: "Forest", genre: "Adventure", content_rating: "family" },
    ]
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => templates,
      } as Response)
    )

    render(<TemplateSelectClient />)

    const option = await screen.findByRole("radio", { name: /select forest/i })
    const user = userEvent.setup()
    await user.click(option)

    await waitFor(() => {
      expect(window.localStorage.getItem("storyfill.templateId")).toBe("t-forest-mishap")
    })

    const continueButton = screen.getByRole("button", { name: /start solo/i })
    expect(continueButton).toBeEnabled()
  })

  it("shows an error state when template loading fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({}),
      } as Response)
    )

    render(<TemplateSelectClient />)

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("load templates")
  })
})
