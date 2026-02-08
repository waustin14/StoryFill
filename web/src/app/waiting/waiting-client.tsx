"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import type { MultiplayerSession } from "@/lib/multiplayer-session"
import {
  clearMultiplayerSession,
  loadMultiplayerSession,
  saveMultiplayerSession,
} from "@/lib/multiplayer-session"

type RoomProgressResponse = {
  assigned_total: number
  submitted_total: number
  connected_total: number
  disconnected_total: number
  ready_to_reveal: boolean
}

type ReconnectPlayerResponse = {
  player_id: string
  player_token: string
  player_display_name: string
  room_snapshot: {
    room_id: string
    room_code: string
    round_id: string
    state_version: number
    locked: boolean
    template_id: string
    players: Array<{ id: string; display_name: string }>
  }
  prompts: Array<{ id: string; label: string; type: string; submitted: boolean }>
}

type RoomSnapshot = {
  room_id: string
  room_code: string
  round_id: string
  state_version: number
  locked: boolean
  template_id: string
  players: Array<{ id: string; display_name: string }>
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

function wsBaseUrl() {
  const base = new URL(API_BASE_URL)
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:"
  base.pathname = "/v1/ws"
  base.search = ""
  return base.toString()
}

export default function WaitingClient() {
  const router = useRouter()
  const [session, setSession] = useState<MultiplayerSession | null>(null)
  const reconnectRef = useRef<string | null>(null)
  const [progress, setProgress] = useState<RoomProgressResponse | null>(null)
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle")
  const [error, setError] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<RoomSnapshot | null>(null)
  const [moderationStatus, setModerationStatus] = useState<"idle" | "loading" | "error">("idle")
  const [moderationError, setModerationError] = useState<string | null>(null)

  const isHost = useMemo(() => session?.role === "host", [session])

  useEffect(() => {
    setSession(loadMultiplayerSession())
  }, [])

  useEffect(() => {
    if (!session || session.role === "host") return

    const reconnectKey = `${session.roomCode}:${session.playerId}:${session.playerToken}`
    if (reconnectRef.current === reconnectKey) return
    reconnectRef.current = reconnectKey

    let active = true
    const reconnect = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/v1/rooms/${session.roomCode}/players/${session.playerId}:reconnect`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ player_token: session.playerToken }),
          }
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (!response.ok) {
          clearMultiplayerSession()
          setSession(null)
          return
        }
        const data = (await response.json()) as ReconnectPlayerResponse
        if (!active) return
        const nextSession = {
          ...session,
          roomCode: data.room_snapshot.room_code,
          roomId: data.room_snapshot.room_id,
          roundId: data.room_snapshot.round_id,
          templateId: data.room_snapshot.template_id ?? null,
          playerId: data.player_id,
          playerToken: data.player_token,
          displayName: data.player_display_name ?? session.displayName ?? null,
        }
        saveMultiplayerSession(nextSession)
        setSession(nextSession)
      } catch {
        if (!active) return
      }
    }
    reconnect()

    return () => {
      active = false
    }
  }, [session, router])

  useEffect(() => {
    if (!session) return

    let ws: WebSocket | null = null
    let alive = true
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null
    let attempts = 0

    type RoomEvent =
      | { type: "room.snapshot"; payload: { room_snapshot: RoomSnapshot; progress: RoomProgressResponse } }
      | { type: "room.expired" }
      | { type: string; payload?: unknown }

    const connect = () => {
      if (!alive) return
      setStatus("loading")
      setError(null)
      setModerationStatus("loading")
      setModerationError(null)

      // Hosts can connect with either hostToken or their playerToken (host is also a player).
      const token =
        session.role === "host" ? (session.hostToken ?? session.playerToken) : session.playerToken
      if (!token) {
        clearMultiplayerSession()
        setSession(null)
        setStatus("error")
        setError("Missing session token. Please rejoin the room.")
        return
      }
      const url = new URL(wsBaseUrl())
      url.searchParams.set("room_code", session.roomCode)
      url.searchParams.set("token", token)

      ws = new WebSocket(url.toString())

      ws.onopen = () => {
        attempts = 0
        heartbeatTimer = setInterval(() => {
          try {
            ws?.send(JSON.stringify({ type: "client.heartbeat", ts: Date.now() }))
          } catch {
            // no-op
          }
        }, 25000)
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as RoomEvent
          if (payload.type === "room.expired") {
            router.push("/expired")
            return
          }
          if (payload.type === "room.snapshot") {
            setSnapshot(payload.payload.room_snapshot)
            setProgress(payload.payload.progress)
            setStatus("ready")
            setError(null)
            setModerationStatus("ready")
            setModerationError(null)
          }
        } catch {
          // ignore malformed events
        }
      }

      const scheduleReconnect = () => {
        if (!alive) return
        attempts += 1
        const backoff = Math.min(1000 * 2 ** attempts, 10000)
        reconnectTimer = setTimeout(connect, backoff)
      }

      ws.onerror = () => {
        if (heartbeatTimer) clearInterval(heartbeatTimer)
        setStatus("error")
        setError("Connection lost. Reconnecting…")
        scheduleReconnect()
      }

      ws.onclose = (event) => {
        if (heartbeatTimer) clearInterval(heartbeatTimer)
        if (event.code === 4404 || event.code === 4410) {
          clearMultiplayerSession()
          router.push("/expired")
          return
        }
        if (event.code === 4400 || event.code === 4403) {
          clearMultiplayerSession()
          router.push("/room")
          return
        }
        setStatus("error")
        setError("Connection lost. Reconnecting…")
        scheduleReconnect()
      }
    }

    connect()

    return () => {
      alive = false
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (heartbeatTimer) clearInterval(heartbeatTimer)
      try {
        ws?.close()
      } catch {
        // ignore
      }
    }
  }, [session, router])

  if (!session) {
    return (
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold">Waiting</h1>
        <p className="text-slate-600 dark:text-slate-300">
          No active multiplayer session found. Return to the lobby to join a room.
        </p>
        <Link
          href="/room"
          className="btn-primary"
        >
          Go to Room Lobby
        </Link>
      </section>
    )
  }

  const assignedTotal = progress?.assigned_total ?? 0
  const submittedTotal = progress?.submitted_total ?? 0
  const connectedTotal = progress?.connected_total ?? 0
  const disconnectedTotal = progress?.disconnected_total ?? 0
  const remaining = Math.max(assignedTotal - submittedTotal, 0)
  const percent = assignedTotal > 0 ? Math.round((submittedTotal / assignedTotal) * 100) : 0

  const readyToReveal = progress?.ready_to_reveal ?? false
  const statusLabel = readyToReveal
    ? isHost
      ? "Ready to reveal"
      : "Waiting for host"
    : "Waiting for others"

  const liveMessage = readyToReveal
    ? isHost
      ? "All prompts submitted. You're ready to reveal the story."
      : "All prompts submitted. Waiting for the host to reveal the story."
    : `Progress update: ${submittedTotal} of ${assignedTotal} prompts submitted. Waiting for ${remaining} more.`

  const hostLocked = snapshot?.locked ?? false
  const hostPlayers = snapshot?.players ?? []

  const toggleRoomLock = async () => {
    if (!session || !isHost) return
    const hostToken = session.hostToken
    if (!hostToken) {
      setModerationStatus("error")
      setModerationError("Missing host token. Please return to the lobby and create a new room.")
      return
    }
    try {
      setModerationStatus("loading")
      setModerationError(null)
      const response = await fetch(
        `${API_BASE_URL}/v1/rooms/${session.roomCode}:${hostLocked ? "unlock" : "lock"}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host_token: hostToken }),
        }
      )
      if (response.status === 410) {
        router.push("/expired")
        return
      }
      if (!response.ok) throw new Error("Unable to update room lock.")
      const data = (await response.json()) as RoomSnapshot
      setSnapshot(data)
      setModerationStatus("ready")
    } catch (err) {
      setModerationStatus("error")
      setModerationError("We couldn't update the room lock. Please try again.")
    }
  }

  const kickPlayer = async (playerId: string) => {
    if (!session || !isHost) return
    const hostToken = session.hostToken
    if (!hostToken) {
      setModerationStatus("error")
      setModerationError("Missing host token. Please return to the lobby and create a new room.")
      return
    }
    try {
      setModerationStatus("loading")
      setModerationError(null)
      const response = await fetch(
        `${API_BASE_URL}/v1/rooms/${session.roomCode}/players/${playerId}:kick`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host_token: hostToken }),
        }
      )
      if (response.status === 410) {
        router.push("/expired")
        return
      }
      if (!response.ok) throw new Error("Unable to remove player.")
      const data = (await response.json()) as RoomSnapshot
      setSnapshot(data)
      setModerationStatus("ready")
    } catch {
      setModerationStatus("error")
      setModerationError("We couldn't kick that player. Please try again.")
    }
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Waiting for the story</h1>
        <p className="text-muted-foreground">
          Progress updates show counts only — no words are revealed until the host shares the story.
        </p>
      </header>

      {status === "error" && error && (
        <div
          className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <div className="rounded-2xl border bg-card p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Room progress
              </p>
              <h2 className="text-xl font-semibold">Collecting prompts</h2>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full border bg-muted px-3 py-1 text-xs font-semibold text-muted-foreground">
              {statusLabel}
            </span>
          </div>

          <div className="mt-6 space-y-4">
            <div
              className="space-y-3 rounded-xl border bg-muted p-4"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={assignedTotal}
              aria-valuenow={submittedTotal}
              aria-label="Prompts submitted"
            >
              <div className="flex items-center justify-between text-sm font-semibold">
                <span>
                  {submittedTotal} of {assignedTotal} prompts submitted
                </span>
                <span className="text-muted-foreground">{percent}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-background">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300"
                  style={{ width: `${percent}%` }}
                />
              </div>
              <div className="grid gap-3 text-xs text-muted-foreground sm:grid-cols-3">
                <div className="rounded-lg border bg-card p-3">
                  <p className="text-sm font-semibold text-foreground">{connectedTotal}</p>
                  <p>Players connected</p>
                </div>
                <div className="rounded-lg border bg-card p-3">
                  <p className="text-sm font-semibold text-foreground">{remaining}</p>
                  <p>Still typing</p>
                </div>
                <div className="rounded-lg border bg-card p-3">
                  <p className="text-sm font-semibold text-foreground">{disconnectedTotal}</p>
                  <p>Disconnected</p>
                </div>
              </div>
            </div>

            <div
              className="rounded-xl border border-dashed bg-card px-4 py-3 text-sm text-muted-foreground"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              {liveMessage}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border bg-card p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {isHost ? "Host view" : "Player view"}
            </p>
            <h2 className="mt-2 text-xl font-semibold">
              {readyToReveal ? (isHost ? "Ready to reveal" : "Waiting for host") : "Waiting for others"}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {readyToReveal
                ? isHost
                  ? "Everyone has submitted. You're the only one who can reveal the story."
                  : "Everyone has submitted. The host will reveal the story soon."
                : "Keep this tab open while the remaining prompts come in."}
            </p>

            <div className="mt-5 flex flex-wrap gap-3">
              {isHost ? (
                <Link
                  href={readyToReveal ? "/reveal" : "#"}
                  onClick={(event) => {
                    if (!readyToReveal) event.preventDefault()
                  }}
                  className={readyToReveal ? "btn-primary" : "btn-primary pointer-events-none"}
                  aria-disabled={!readyToReveal}
                >
                  Reveal Story
                </Link>
              ) : (
                <button
                  type="button"
                  disabled
                  className="btn-primary"
                >
                  Waiting for host
                </button>
              )}
              <Link
                href="/lobby"
                className="btn-secondary"
              >
                Back to lobby
              </Link>
            </div>
          </div>

          {isHost && (
            <div className="rounded-2xl border bg-card p-6 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Moderation
              </p>
              <h2 className="mt-2 text-xl font-semibold">Room controls</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Lock the room to stop new joins, or remove disruptive players.
              </p>

              {moderationStatus === "error" && moderationError && (
                <div
                  className="mt-4 rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
                  role="alert"
                >
                  {moderationError}
                </div>
              )}

              <div className="mt-4 rounded-xl border bg-muted p-4 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      Room status
                    </p>
                    <p className="mt-2 text-base font-semibold">
                      {hostLocked ? "Room locked" : "Room open"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={toggleRoomLock}
                    disabled={moderationStatus === "loading"}
                    className="btn-secondary"
                  >
                    {moderationStatus === "loading"
                      ? "Updating..."
                      : hostLocked
                        ? "Unlock room"
                        : "Lock room"}
                  </button>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Players
                </p>
                {hostPlayers.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No players yet.</p>
                ) : (
                  <ul className="space-y-2">
                    {hostPlayers.map((player) => (
                      <li
                        key={player.id}
                        className="flex items-center justify-between rounded-lg border bg-card px-3 py-2 text-sm"
                      >
                        <span className="font-medium text-foreground">{player.display_name}</span>
                        <button
                          type="button"
                          onClick={() => kickPlayer(player.id)}
                          disabled={moderationStatus === "loading"}
                          className={`rounded-full border border-rose-300 px-3 py-1 text-xs font-semibold text-rose-700 transition hover:border-rose-400 hover:text-rose-800 dark:border-rose-900/60 dark:text-rose-200 ${
                            moderationStatus === "loading" ? "cursor-not-allowed opacity-70" : ""
                          }`}
                        >
                          Kick
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
