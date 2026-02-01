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
  locked: boolean
  template_id: string
  players: Array<{ id: string; display_name: string }>
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

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

  const isHost = useMemo(() => session?.playerId === "host", [session])

  useEffect(() => {
    setSession(loadMultiplayerSession())
  }, [])

  useEffect(() => {
    if (!session || session.playerId === "host") return

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
  }, [session])

  useEffect(() => {
    if (!session) return

    let active = true
    let timer: ReturnType<typeof setInterval> | null = null

    const loadProgress = async () => {
      try {
        if (!active) return
        setStatus((prev) => (prev === "ready" ? "ready" : "loading"))
        const response = await fetch(
          `${API_BASE_URL}/v1/rooms/${session.roomCode}/rounds/${session.roundId}/progress`
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (!response.ok) throw new Error("Unable to load progress.")
        const data = (await response.json()) as RoomProgressResponse
        if (!active) return
        setProgress(data)
        setStatus("ready")
        setError(null)
      } catch (err) {
        if (!active) return
        setStatus("error")
        setError("We couldn't refresh room progress. Retrying...")
      }
    }

    loadProgress()
    timer = setInterval(loadProgress, 3000)

    return () => {
      active = false
      if (timer) clearInterval(timer)
    }
  }, [session])

  useEffect(() => {
    if (!session || !isHost) return

    let active = true
    let timer: ReturnType<typeof setInterval> | null = null

    const loadSnapshot = async () => {
      try {
        if (!active) return
        setModerationStatus((prev) => (prev === "ready" ? "ready" : "loading"))
        const response = await fetch(
          `${API_BASE_URL}/v1/rooms/${session.roomCode}:snapshot?host_token=${encodeURIComponent(
            session.playerToken
          )}`
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (!response.ok) throw new Error("Unable to load room controls.")
        const data = (await response.json()) as RoomSnapshot
        if (!active) return
        setSnapshot(data)
        setModerationStatus("ready")
        setModerationError(null)
      } catch {
        if (!active) return
        setModerationStatus("error")
        setModerationError("We couldn't refresh host controls. Retrying...")
      }
    }

    loadSnapshot()
    timer = setInterval(loadSnapshot, 5000)

    return () => {
      active = false
      if (timer) clearInterval(timer)
    }
  }, [session, isHost])

  if (!session) {
    return (
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold">Waiting</h1>
        <p className="text-slate-600 dark:text-slate-300">
          No active multiplayer session found. Return to the lobby to join a room.
        </p>
        <Link
          href="/room"
          className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
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
    try {
      setModerationStatus("loading")
      setModerationError(null)
      const response = await fetch(
        `${API_BASE_URL}/v1/rooms/${session.roomCode}:${hostLocked ? "unlock" : "lock"}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host_token: session.playerToken }),
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
    try {
      setModerationStatus("loading")
      setModerationError(null)
      const response = await fetch(
        `${API_BASE_URL}/v1/rooms/${session.roomCode}/players/${playerId}:kick`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host_token: session.playerToken }),
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
        <p className="text-slate-600 dark:text-slate-300">
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
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                Room progress
              </p>
              <h2 className="text-xl font-semibold">Collecting prompts</h2>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-300">
              {statusLabel}
            </span>
          </div>

          <div className="mt-6 space-y-4">
            <div
              className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/40"
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
                <span className="text-slate-500 dark:text-slate-300">{percent}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                <div
                  className="h-full rounded-full bg-slate-900 transition-[width] duration-300 dark:bg-slate-100"
                  style={{ width: `${percent}%` }}
                />
              </div>
              <div className="grid gap-3 text-xs text-slate-500 sm:grid-cols-3 dark:text-slate-400">
                <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {connectedTotal}
                  </p>
                  <p>Players connected</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {remaining}
                  </p>
                  <p>Still typing</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {disconnectedTotal}
                  </p>
                  <p>Disconnected</p>
                </div>
              </div>
            </div>

            <div
              className="rounded-lg border border-dashed border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              {liveMessage}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-950">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
              {isHost ? "Host view" : "Player view"}
            </p>
            <h2 className="mt-2 text-xl font-semibold">
              {readyToReveal ? (isHost ? "Ready to reveal" : "Waiting for host") : "Waiting for others"}
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
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
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    readyToReveal
                      ? "bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
                      : "cursor-not-allowed bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                  }`}
                  aria-disabled={!readyToReveal}
                >
                  Reveal Story
                </Link>
              ) : (
                <button
                  type="button"
                  disabled
                  className="rounded-full bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                >
                  Waiting for host
                </button>
              )}
              <Link
                href="/room"
                className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
              >
                Back to lobby
              </Link>
            </div>
          </div>

          {isHost && (
            <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-950">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                Moderation
              </p>
              <h2 className="mt-2 text-xl font-semibold">Room controls</h2>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
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

              <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/40">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
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
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                      hostLocked
                        ? "border border-slate-300 text-slate-700 hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
                        : "bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
                    } ${moderationStatus === "loading" ? "cursor-not-allowed opacity-70" : ""}`}
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
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                  Players
                </p>
                {hostPlayers.length === 0 ? (
                  <p className="text-sm text-slate-600 dark:text-slate-300">No players yet.</p>
                ) : (
                  <ul className="space-y-2">
                    {hostPlayers.map((player) => (
                      <li
                        key={player.id}
                        className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-950"
                      >
                        <span className="font-medium text-slate-700 dark:text-slate-200">
                          {player.display_name}
                        </span>
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
