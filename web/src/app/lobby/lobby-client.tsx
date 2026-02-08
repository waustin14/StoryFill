"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import type { MultiplayerSession } from "@/lib/multiplayer-session"
import { clearMultiplayerSession, loadMultiplayerSession } from "@/lib/multiplayer-session"

type RoomSnapshot = {
  room_id: string
  room_code: string
  round_id: string
  state_version: number
  room_state: string
  locked: boolean
  template_id: string
  players: Array<{ id: string; display_name: string }>
}

type RoomProgressResponse = {
  assigned_total: number
  submitted_total: number
  connected_total: number
  disconnected_total: number
  ready_to_reveal: boolean
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

function wsBaseUrl() {
  const base = new URL(API_BASE_URL)
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:"
  base.pathname = "/v1/ws"
  base.search = ""
  return base.toString()
}

export default function LobbyClient() {
  const router = useRouter()
  const [session, setSession] = useState<MultiplayerSession | null>(null)
  const [snapshot, setSnapshot] = useState<RoomSnapshot | null>(null)
  const [progress, setProgress] = useState<RoomProgressResponse | null>(null)
  const [status, setStatus] = useState<"idle" | "connecting" | "ready" | "error">("idle")
  const [error, setError] = useState<string | null>(null)
  const startStatusRef = useRef<"idle" | "starting">("idle")

  const isHost = useMemo(() => session?.role === "host", [session])

  useEffect(() => {
    setSession(loadMultiplayerSession())
  }, [])

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
      setStatus("connecting")
      setError(null)

      const token =
        session.role === "host" ? (session.hostToken ?? session.playerToken) : session.playerToken
      if (!token) {
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
            // ignore
          }
        }, 25000)
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as RoomEvent
          if (payload.type === "room.expired") {
            clearMultiplayerSession()
            router.push("/expired")
            return
          }
          if (payload.type === "room.snapshot") {
            setSnapshot(payload.payload.room_snapshot)
            setProgress(payload.payload.progress)
            setStatus("ready")
            setError(null)

            const nextState = payload.payload.room_snapshot.room_state
            if (nextState !== "LobbyOpen") {
              router.push("/prompting")
            }
          }
        } catch {
          // ignore malformed
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
        <h1 className="text-2xl font-semibold">Lobby</h1>
        <p className="text-muted-foreground">No active room session found.</p>
        <Link href="/room" className="btn-primary">
          Create or join a room
        </Link>
      </section>
    )
  }

  const roomCode = snapshot?.room_code ?? session.roomCode
  const players = snapshot?.players ?? []
  const locked = snapshot?.locked ?? false
  const canStart = isHost && players.length >= 2 && !locked

  const startGame = async () => {
    if (!isHost || !session.hostToken) return
    if (startStatusRef.current === "starting") return
    startStatusRef.current = "starting"
    try {
      const response = await fetch(`${API_BASE_URL}/v1/rooms/${session.roomCode}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host_token: session.hostToken }),
      })
      if (response.status === 410) {
        clearMultiplayerSession()
        router.push("/expired")
        return
      }
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail || "Unable to start the game.")
      }
      router.push("/prompting")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to start the game."
      setError(message)
    } finally {
      startStatusRef.current = "idle"
    }
  }

  const toggleLock = async () => {
    if (!isHost || !session.hostToken) return
    try {
      setError(null)
      const endpoint = locked ? ":unlock" : ":lock"
      const response = await fetch(`${API_BASE_URL}/v1/rooms/${session.roomCode}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host_token: session.hostToken }),
      })
      if (response.status === 410) {
        clearMultiplayerSession()
        router.push("/expired")
        return
      }
      if (!response.ok) throw new Error("Unable to update room settings.")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to update room settings."
      setError(message)
    }
  }

  const leaveRoom = async () => {
    if (isHost) return
    try {
      setError(null)
      const response = await fetch(`${API_BASE_URL}/v1/rooms/${session.roomCode}/leave`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_id: session.playerId, player_token: session.playerToken }),
      })
      if (!response.ok) throw new Error("Unable to leave the room.")
      clearMultiplayerSession()
      router.push("/room")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to leave the room."
      setError(message)
    }
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Room lobby</p>
        <h1 className="text-2xl font-semibold">Get ready</h1>
        <p className="text-muted-foreground">
          {isHost ? "Invite players, then start the game." : "Waiting for the host to start the game."}
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4 shadow-sm">
        <div className="space-y-1">
          <p className="text-sm font-semibold">Room code</p>
          <p className="mono-chip inline-flex">{roomCode}</p>
        </div>
        <div className="text-sm text-muted-foreground">
          {status === "connecting" ? "Connecting…" : status === "error" ? "Reconnecting…" : "Live"}
        </div>
      </div>

      <div className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Players</h2>
            <p className="text-sm text-muted-foreground">
              {players.length === 0 ? "Waiting for players to join…" : `${players.length} player(s) in room`}
            </p>
          </div>
          {isHost ? (
            <button type="button" onClick={toggleLock} className="btn-outline">
              {locked ? "Unlock room" : "Lock room"}
            </button>
          ) : (
            <button type="button" onClick={leaveRoom} className="btn-outline">
              Leave room
            </button>
          )}
        </div>

        <div className="mt-4 grid gap-2">
          {players.map((player) => (
            <div key={player.id} className="flex items-center justify-between rounded-lg border bg-background px-4 py-3">
              <span className="font-medium">{player.display_name}</span>
              <span className="text-xs text-muted-foreground">Joined</span>
            </div>
          ))}
        </div>

        {isHost && (
          <div className="mt-5 space-y-2">
            <button type="button" onClick={startGame} className="btn-primary" disabled={!canStart}>
              Start game
            </button>
            {!canStart && (
              <p className="text-sm text-muted-foreground">
                {locked
                  ? "Room is locked. Unlock to allow new players."
                  : "Waiting for at least 2 players before starting."}
              </p>
            )}
          </div>
        )}
      </div>

      {progress && snapshot?.room_state !== "LobbyOpen" && (
        <div className="rounded-xl border bg-card p-4 text-sm text-muted-foreground shadow-sm">
          Game started: {progress.submitted_total} / {progress.assigned_total} prompts submitted.
        </div>
      )}
    </section>
  )
}
