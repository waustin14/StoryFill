"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { saveMultiplayerSession } from "@/lib/multiplayer-session"

type CreateRoomResponse = {
  room_code: string
  room_id: string
  round_id: string
  host_token: string
  ws_url: string
  template_id: string
}

type JoinRoomResponse = {
  player_id: string
  player_token: string
  player_display_name: string
  room_snapshot: {
    room_id: string
    room_code: string
    round_id: string
    locked: boolean
    template_id: string
    players: Array<{ id: string; display_name: string }>
  }
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
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
        body: JSON.stringify({ template_id: templateId || null }),
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
        playerId: "host",
        playerToken: data.host_token,
        createdAt: new Date().toISOString(),
      })
      setCreateStatus("done")
      router.push("/prompting")
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
        playerId: data.player_id,
        playerToken: data.player_token,
        displayName: data.player_display_name ?? displayName ?? null,
        createdAt: new Date().toISOString(),
      })
      setJoinStatus("done")
      router.push("/prompting")
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
        <h1 className="text-2xl font-semibold">Room Lobby</h1>
        <p className="text-slate-600 dark:text-slate-300">
          Create a room as host or join an existing room with a code.
        </p>
      </header>

      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {createStatus === "loading" && "Creating room."}
        {createStatus === "done" && "Room created. Redirecting to prompts."}
        {createStatus === "error" && "Room creation failed."}
        {joinStatus === "loading" && "Joining room."}
        {joinStatus === "done" && "Joined room. Redirecting to prompts."}
        {joinStatus === "error" && "Unable to join room."}
      </div>

      {error && (
        <div
          className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
          <h2 className="text-lg font-semibold">Host a Room</h2>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Start a lobby and share the room code with friends.
          </p>
          <button
            type="button"
            onClick={handleCreateRoom}
            className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
          >
            {createStatus === "loading" ? "Creating..." : "Create Room"}
          </button>

          {createdRoom && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/40">
              <p className="text-slate-600 dark:text-slate-300">Room Code</p>
              <p className="text-xl font-semibold">{createdRoom.room_code}</p>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                Round: {createdRoom.round_id}
              </p>
            </div>
          )}
        </div>

        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
          <h2 className="text-lg font-semibold">Join a Room</h2>
          <form className="space-y-3" onSubmit={handleJoinRoom}>
            <label className="block text-sm font-semibold text-slate-500 dark:text-slate-400">
              Room Code
              <input
                value={roomCode}
                onChange={(event) => setRoomCode(event.target.value.toUpperCase())}
                placeholder="ABC123"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-400 dark:border-slate-700 dark:bg-slate-950"
                required
              />
            </label>
            <label className="block text-sm font-semibold text-slate-500 dark:text-slate-400">
              Display Name (optional)
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Player name"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-400 dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            <button
              type="submit"
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
            >
              {joinStatus === "loading" ? "Joining..." : "Join Room"}
            </button>
          </form>

          {joinedRoom && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/40">
              <p className="text-slate-600 dark:text-slate-300">Players</p>
              <ul className="mt-2 space-y-1">
                {joinedRoom.room_snapshot.players.map((player) => (
                  <li key={player.id} className="text-slate-700 dark:text-slate-200">
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
