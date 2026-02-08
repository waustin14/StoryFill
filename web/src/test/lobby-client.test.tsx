import { act, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import LobbyClient from "@/app/lobby/lobby-client"

const pushMock = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}))

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  url: string
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
    setTimeout(() => this.onopen?.(), 0)
  }

  send() {}
  close() {}

  triggerMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent)
  }
}

const snapshotPayload = {
  type: "room.snapshot",
  payload: {
    room_snapshot: {
      room_id: "room_1",
      room_code: "ABC123",
      round_id: "round_1",
      state_version: 1,
      room_state: "LobbyOpen",
      locked: false,
      template_id: "t-forest-mishap",
      players: [
        { id: "player_1", display_name: "Host" },
        { id: "player_2", display_name: "Guest" },
      ],
    },
    progress: {
      assigned_total: 0,
      submitted_total: 0,
      connected_total: 2,
      disconnected_total: 0,
      ready_to_reveal: false,
    },
  },
}

describe("LobbyClient", () => {
  beforeEach(() => {
    pushMock.mockClear()
    window.localStorage.clear()
    FakeWebSocket.instances = []
    vi.stubGlobal("WebSocket", FakeWebSocket)
  })

  it("renders host controls when role is host", async () => {
    window.localStorage.setItem(
      "storyfill.multiplayerSession",
      JSON.stringify({
        roomCode: "ABC123",
        roomId: "room_1",
        roundId: "round_1",
        templateId: "t-forest-mishap",
        role: "host",
        playerId: "player_1",
        playerToken: "player-token",
        hostToken: "host-token",
        displayName: "Host",
        createdAt: new Date().toISOString(),
      })
    )

    render(<LobbyClient />)

    await waitFor(() => {
      expect(FakeWebSocket.instances.length).toBeGreaterThan(0)
    })
    const ws = FakeWebSocket.instances.at(-1)
    if (ws) {
      act(() => {
        ws.triggerMessage(snapshotPayload)
      })
    }

    expect(await screen.findByRole("button", { name: /start game/i })).toBeEnabled()
    expect(screen.getByRole("button", { name: /lock room/i })).toBeInTheDocument()
  })

  it("renders player controls when role is player", async () => {
    window.localStorage.setItem(
      "storyfill.multiplayerSession",
      JSON.stringify({
        roomCode: "ABC123",
        roomId: "room_1",
        roundId: "round_1",
        templateId: "t-forest-mishap",
        role: "player",
        playerId: "player_2",
        playerToken: "player-token",
        displayName: "Guest",
        createdAt: new Date().toISOString(),
      })
    )

    render(<LobbyClient />)

    await waitFor(() => {
      expect(FakeWebSocket.instances.length).toBeGreaterThan(0)
    })
    const ws = FakeWebSocket.instances.at(-1)
    if (ws) {
      act(() => {
        ws.triggerMessage(snapshotPayload)
      })
    }

    expect(await screen.findByRole("button", { name: /leave room/i })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /lock room/i })).toBeNull()
    expect(screen.queryByRole("button", { name: /start game/i })).toBeNull()
  })
})
