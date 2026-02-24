"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { AlertTriangle } from "lucide-react"

import { API_BASE_URL } from "@/lib/api"
import { saveMultiplayerSession } from "@/lib/multiplayer-session"

type CreateRoomResponse = {
  room_code: string
  room_id: string
  round_id: string
  player_id: string
  player_token: string
  player_display_name: string
  host_token: string
  ws_url: string
  template_id: string
  room_snapshot: {
    room_id: string
    room_code: string
    round_id: string
    state_version: number
    room_state: string
    locked: boolean
    template_id: string
    players: Array<{ id: string; display_name: string }>
  }
}

type JoinRoomResponse = {
  player_id: string
  player_token: string
  player_display_name: string
  room_snapshot: {
    room_id: string
    room_code: string
    round_id: string
    state_version: number
    room_state: string
    locked: boolean
    template_id: string
    players: Array<{ id: string; display_name: string }>
  }
}

const TEMPLATE_STORAGE_KEY = "storyfill.templateId"

export default function RoomLobbyClient() {
  const router = useRouter()
  const [createStatus, setCreateStatus] = useState<"idle" | "loading" | "done" | "error">("idle")
  const [joinStatus, setJoinStatus] = useState<"idle" | "loading" | "done" | "error">("idle")
  const [roomCode, setRoomCode] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [createdRoom, setCreatedRoom] = useState<CreateRoomResponse | null>(null)
  const [joinedRoom, setJoinedRoom] = useState<JoinRoomResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleCreateRoom() {
    setError(null)
    setCreateStatus("loading")
    try {
      const templateId = window.localStorage.getItem(TEMPLATE_STORAGE_KEY)
      const response = await fetch(`${API_BASE_URL}/v1/rooms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template_id: templateId || null, display_name: displayName || null }),
      })
      if (!response.ok) {
        if (response.status === 429) {
          const payload = (await response.json()) as { detail?: string }
          throw new Error(payload.detail || "Too many rooms created. Please try again soon.")
        }
        throw new Error("Failed to create room.")
      }
      const data = (await response.json()) as CreateRoomResponse
      setCreatedRoom(data)
      saveMultiplayerSession({
        roomCode: data.room_code,
        roomId: data.room_id,
        roundId: data.round_id,
        templateId: data.template_id ?? null,
        role: "host",
        playerId: data.player_id,
        playerToken: data.player_token,
        hostToken: data.host_token,
        displayName: data.player_display_name ?? null,
        createdAt: new Date().toISOString(),
      })
      setCreateStatus("done")
      router.push("/templates?mode=multiplayer")
    } catch (err) {
      setCreateStatus("error")
      const message = err instanceof Error ? err.message : "Unable to create a room right now."
      setError(message)
    }
  }

  async function handleJoinRoom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setJoinStatus("loading")
    try {
      const response = await fetch(`${API_BASE_URL}/v1/rooms/${roomCode.trim()}/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName || null }),
      })
      if (response.status === 410) {
        setJoinStatus("error")
        setError("That room has expired. Ask the host to start a new room.")
        return
      }
      if (!response.ok) {
        if (response.status === 403) {
          setJoinStatus("error")
          setError("That room is locked. Ask the host to unlock it.")
          return
        }
        if (response.status === 409) {
          const payload = (await response.json()) as { detail?: string }
          setJoinStatus("error")
          setError(payload.detail || "That room is full.")
          return
        }
        if (response.status === 429) {
          const payload = (await response.json()) as { detail?: string }
          setJoinStatus("error")
          setError(payload.detail || "Too many join attempts. Please wait and try again.")
          return
        }
        throw new Error("Failed to join room.")
      }
      const data = (await response.json()) as JoinRoomResponse
      setJoinedRoom(data)
      saveMultiplayerSession({
        roomCode: data.room_snapshot.room_code,
        roomId: data.room_snapshot.room_id,
        roundId: data.room_snapshot.round_id,
        templateId: data.room_snapshot.template_id ?? null,
        role: "player",
        playerId: data.player_id,
        playerToken: data.player_token,
        displayName: data.player_display_name ?? displayName ?? null,
        createdAt: new Date().toISOString(),
      })
      setJoinStatus("done")
      router.push("/templates?mode=multiplayer")
    } catch (err) {
      setJoinStatus("error")
      const message =
        err instanceof Error ? err.message : "Unable to join that room. Check the code and try again."
      setError(message)
    }
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-3xl font-bold tracking-tight md:text-4xl">Room Lobby</h1>
        <p className="text-muted-foreground">
          Create a room as host or join an existing room with a code.
        </p>
      </header>

      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {createStatus === "loading" && "Creating room."}
        {createStatus === "done" && "Room created. Redirecting to templates."}
        {createStatus === "error" && "Room creation failed."}
        {joinStatus === "loading" && "Joining room."}
        {joinStatus === "done" && "Joined room. Redirecting to templates."}
        {joinStatus === "error" && "Unable to join room."}
      </div>

      {error && (
        <div className="alert-error" role="alert">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4 rounded-2xl border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Host a Room</h2>
          <p className="text-sm text-muted-foreground">
            Start a lobby and share the room code with friends.
          </p>
          <button
            type="button"
            onClick={handleCreateRoom}
            className="btn-secondary"
          >
            {createStatus === "loading" ? "Creating…" : "Create Room"}
          </button>

          {createdRoom && (
            <div className="rounded-xl border bg-muted/50 p-4 text-sm">
              <p className="font-mono text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">
                Room code
              </p>
              <p className="mt-3">
                <span className="mono-chip">{createdRoom.room_code}</span>
              </p>
              <p className="mt-3 text-xs text-muted-foreground">Round: {createdRoom.round_id}</p>
            </div>
          )}
        </div>

        <div className="space-y-4 rounded-2xl border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Join a Room</h2>
          <form className="space-y-4" onSubmit={handleJoinRoom}>
            <label className="block text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Room Code
              <input
                value={roomCode}
                onChange={(event) => setRoomCode(event.target.value.toUpperCase())}
                placeholder="ABC123"
                className="mt-2 w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-ring"
                required
              />
            </label>
            <label className="block text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Display Name (optional)
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Player name"
                maxLength={30}
                className="mt-2 w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-ring"
              />
            </label>
            <button
              type="submit"
              className="btn-primary"
            >
              {joinStatus === "loading" ? "Joining…" : "Join Room"}
            </button>
          </form>

          {joinedRoom && (
            <div className="rounded-xl border bg-muted/50 p-4 text-sm">
              <p className="font-mono text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">
                Players
              </p>
              <ul className="mt-2 space-y-1">
                {joinedRoom.room_snapshot.players.map((player) => (
                  <li key={player.id} className="text-foreground">
                    {player.display_name}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
