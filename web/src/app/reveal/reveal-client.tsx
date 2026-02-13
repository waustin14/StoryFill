"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AlertTriangle, Pause, Play, Share2, Sparkles, Square, Volume2 } from "lucide-react"

import type { SoloSession } from "@/lib/solo-session"
import { loadSoloSession, restartSoloRound, saveSoloSession } from "@/lib/solo-session"
import type { MultiplayerSession } from "@/lib/multiplayer-session"
import {
  clearMultiplayerSession,
  loadMultiplayerSession,
  saveMultiplayerSession,
} from "@/lib/multiplayer-session"
import { renderStory } from "@/lib/story-renderer"
import { ttsStatusLabel } from "@/lib/tts-status"

type RevealRoomResponse = {
  room_id: string
  round_id: string
  rendered_story: string
}

type StoryResponse = {
  room_id: string
  round_id: string
  rendered_story: string
}

type RoomProgressResponse = {
  assigned_total: number
  submitted_total: number
  connected_total: number
  disconnected_total: number
  ready_to_reveal: boolean
}

type RoomSnapshot = {
  room_id: string
  room_code: string
  round_id: string
  round_index: number
  state_version: number
  room_state: string
  locked: boolean
  template_id: string
  players: Array<{ id: string; display_name: string; is_host?: boolean }>
}

type ReplayRoomResponse = {
  room_id: string
  round_id: string
}

type TTSStatusResponse = {
  job_id: string | null
  status: string
  playback_state?: string | null
  audio_url?: string | null
  error_code?: string | null
  error_message?: string | null
  from_cache?: boolean | null
}

type ShareRoomResponse = {
  share_token: string
  share_url: string
  expires_at: string
}

type ReconnectPlayerResponse = {
  player_id: string
  player_token: string
  player_display_name: string
  room_snapshot: RoomSnapshot
  prompts: Array<{ id: string; label: string; type: string; submitted: boolean }>
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

function wsBaseUrl() {
  const base = new URL(API_BASE_URL)
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:"
  base.pathname = "/v1/ws"
  base.search = ""
  return base.toString()
}

export default function RevealClient() {
  const router = useRouter()
  const storyRef = useRef<HTMLDivElement | null>(null)
  const storyValueRef = useRef<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const reconnectRef = useRef<string | null>(null)
  const [soloSession, setSoloSession] = useState<SoloSession | null>(null)
  const [multiplayerSession, setMultiplayerSession] = useState<MultiplayerSession | null>(null)
  const [story, setStory] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [readyToReveal, setReadyToReveal] = useState(false)
  const [ttsJobId, setTtsJobId] = useState<string | null>(null)
  const [ttsStatus, setTtsStatus] = useState<string>("idle")
  const [ttsPlayback, setTtsPlayback] = useState<string>("idle")
  const [ttsAudioUrl, setTtsAudioUrl] = useState<string | null>(null)
  const [ttsError, setTtsError] = useState<string | null>(null)
  const [ttsFromCache, setTtsFromCache] = useState(false)
  const [shareStatus, setShareStatus] = useState<"idle" | "loading" | "ready" | "error">("idle")
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [shareExpiresAt, setShareExpiresAt] = useState<string | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [roundIndex, setRoundIndex] = useState<number>(0)

  useEffect(() => {
    setSoloSession(loadSoloSession())
    setMultiplayerSession(loadMultiplayerSession())
  }, [])

  useEffect(() => {
    storyValueRef.current = story
  }, [story])

  useEffect(() => {
    if (!multiplayerSession || multiplayerSession.role === "host") return

    const reconnectKey = `${multiplayerSession.roomCode}:${multiplayerSession.playerId}:${multiplayerSession.playerToken}`
    if (reconnectRef.current === reconnectKey) return
    reconnectRef.current = reconnectKey

    let active = true
    const reconnect = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/players/${multiplayerSession.playerId}:reconnect`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ player_token: multiplayerSession.playerToken }),
          }
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (!response.ok) {
          clearMultiplayerSession()
          setMultiplayerSession(null)
          return
        }
        const data = (await response.json()) as ReconnectPlayerResponse
        if (!active) return
        const nextSession = {
          ...multiplayerSession,
          roomCode: data.room_snapshot.room_code,
          roomId: data.room_snapshot.room_id,
          roundId: data.room_snapshot.round_id,
          templateId: data.room_snapshot.template_id ?? null,
          playerId: data.player_id,
          playerToken: data.player_token,
          displayName: data.player_display_name ?? multiplayerSession.displayName ?? null,
        }
        saveMultiplayerSession(nextSession)
        setMultiplayerSession(nextSession)
      } catch {
        if (!active) return
      }
    }
    reconnect()

    return () => {
      active = false
    }
  }, [multiplayerSession, router])

  useEffect(() => {
    if (!multiplayerSession) return
    setShareStatus("idle")
    setShareUrl(null)
    setShareExpiresAt(null)
    setShareError(null)
  }, [multiplayerSession])

  const mode = useMemo(() => {
    if (soloSession) return "solo"
    if (multiplayerSession) return "multi"
    return "none"
  }, [soloSession, multiplayerSession])

  const isHost = useMemo(
    () => multiplayerSession?.role === "host",
    [multiplayerSession]
  )

  const soloReady = useMemo(() => {
    return soloSession?.prompts.every((prompt) => prompt.value && prompt.value.trim()) ?? false
  }, [soloSession])

  const soloStory = useMemo(() => {
    if (!soloSession || !soloReady) return null
    return renderStory(soloSession.story, soloSession.slots, soloSession.prompts)
  }, [soloSession, soloReady])

  const normalizeAudioUrl = (url: string | null | undefined) => {
    if (!url) return null
    if (url.startsWith("http://") || url.startsWith("https://")) return url
    if (url.startsWith("/")) {
      return `${API_BASE_URL}${url}`
    }
    return `${API_BASE_URL}/${url}`
  }

  useEffect(() => {
    if (mode !== "multi" || !multiplayerSession) return

    let ws: WebSocket | null = null
    let alive = true
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null
    let attempts = 0

    type RoomEvent =
      | { type: "room.snapshot"; payload: { room_snapshot: RoomSnapshot; progress: RoomProgressResponse } }
      | { type: "room.expired" }
      | { type: string; payload?: unknown }

    const loadStoryOnce = async (roundId: string) => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/rounds/${roundId}/story`
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (response.status === 409) {
          // Rare race: snapshot arrives before story is readable. Retry once shortly.
          setTimeout(() => {
            if (!alive) return
            void loadStoryOnce(roundId)
          }, 600)
          return
        }
        if (!response.ok) throw new Error("Unable to load story.")
        const data = (await response.json()) as StoryResponse
        if (!alive) return
        setStory(data.rendered_story)
        setError(null)
      } catch {
        if (!alive) return
        setError("We couldn't load the story yet. Please try again.")
      }
    }

    const connect = () => {
      if (!alive) return
      setError(null)

      const token = multiplayerSession.playerToken
      if (!token) {
        clearMultiplayerSession()
        setMultiplayerSession(null)
        setError("Missing session token. Please rejoin the room.")
        return
      }
      const url = new URL(wsBaseUrl())
      url.searchParams.set("room_code", multiplayerSession.roomCode)
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
          if (payload.type !== "room.snapshot") return

          const snapshotEvent = payload as { type: "room.snapshot"; payload: { room_snapshot: RoomSnapshot; progress: RoomProgressResponse } }
          const nextSnapshot = snapshotEvent.payload.room_snapshot
          const nextProgress = snapshotEvent.payload.progress
          setReadyToReveal(Boolean(nextProgress.ready_to_reveal))
          if (nextSnapshot.round_index != null) setRoundIndex(nextSnapshot.round_index)

          // Keep local session aligned with the server (e.g., replay creates a new round_id).
          if (
            nextSnapshot.round_id !== multiplayerSession.roundId ||
            nextSnapshot.template_id !== multiplayerSession.templateId ||
            nextSnapshot.room_code !== multiplayerSession.roomCode
          ) {
            const nextSession = {
              ...multiplayerSession,
              roomCode: nextSnapshot.room_code,
              roomId: nextSnapshot.room_id,
              roundId: nextSnapshot.round_id,
              templateId: nextSnapshot.template_id ?? null,
            }
            saveMultiplayerSession(nextSession)
            setMultiplayerSession(nextSession)

            if (nextSnapshot.round_id !== multiplayerSession.roundId && nextSnapshot.room_state !== "Revealed") {
              router.push("/prompting")
              return
            }
          }

          if (nextSnapshot.room_state !== "Revealed" && storyValueRef.current) {
            // New round started or host ended replay; clear the revealed view.
            setStory(null)
          }

          if (nextSnapshot.room_state === "Revealed" && !storyValueRef.current) {
            void loadStoryOnce(nextSnapshot.round_id)
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
        setError("Connection lost. Reconnecting…")
        scheduleReconnect()
      }

      ws.onclose = (event) => {
        if (heartbeatTimer) clearInterval(heartbeatTimer)
        if (event.code === 4404 || event.code === 4410) {
          clearMultiplayerSession()
          setMultiplayerSession(null)
          router.push("/expired")
          return
        }
        if (event.code === 4400 || event.code === 4403) {
          clearMultiplayerSession()
          setMultiplayerSession(null)
          router.push("/room")
          return
        }
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
        // no-op
      }
    }
  }, [mode, multiplayerSession, router])

  useEffect(() => {
    if (mode !== "multi" || !multiplayerSession || !story) {
      return
    }

    const TERMINAL_STATUSES = new Set(["ready", "from_cache", "blocked"])
    let active = true
    let timer: ReturnType<typeof setInterval> | null = null

    const loadTtsStatus = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/rounds/${multiplayerSession.roundId}/tts`
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (!response.ok) throw new Error("Unable to load narration status.")
        const data = (await response.json()) as TTSStatusResponse
        if (!active) return
        setTtsJobId(data.job_id ?? null)
        setTtsStatus(data.status ?? "idle")
        setTtsPlayback(data.playback_state ?? "idle")
        setTtsAudioUrl(normalizeAudioUrl(data.audio_url))
        setTtsError(data.error_message ?? null)
        setTtsFromCache(Boolean(data.from_cache))
        if (data.status && TERMINAL_STATUSES.has(data.status) && timer) {
          clearInterval(timer)
          timer = null
        }
      } catch {
        if (!active) return
        setTtsStatus((prev) => (prev === "idle" ? "idle" : prev))
      }
    }

    loadTtsStatus()
    timer = setInterval(loadTtsStatus, 2500)

    return () => {
      active = false
      if (timer) clearInterval(timer)
    }
  }, [mode, multiplayerSession, story, router])

  useEffect(() => {
    if (mode !== "solo" || !ttsJobId) return

    const TERMINAL_STATUSES = new Set(["ready", "from_cache", "blocked", "error"])
    if (TERMINAL_STATUSES.has(ttsStatus)) return

    let active = true
    const timer = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/v1/tts/jobs/${ttsJobId}`)
        if (!response.ok) return
        const data = (await response.json()) as TTSStatusResponse
        if (!active) return
        setTtsStatus(data.status ?? ttsStatus)
        setTtsPlayback(data.playback_state ?? ttsPlayback)
        setTtsAudioUrl(normalizeAudioUrl(data.audio_url))
        setTtsError(data.error_message ?? null)
        setTtsFromCache(Boolean(data.from_cache))
        if (data.status && TERMINAL_STATUSES.has(data.status)) {
          clearInterval(timer)
        }
      } catch {
        // retry on next tick
      }
    }, 2500)

    return () => {
      active = false
      clearInterval(timer)
    }
  }, [mode, ttsJobId, ttsStatus])

  useEffect(() => {
    if (!audioRef.current) return
    if (!ttsAudioUrl) return
    audioRef.current.src = ttsAudioUrl
    audioRef.current.load()
  }, [ttsAudioUrl])

  useEffect(() => {
    const activeStory = mode === "solo" ? soloStory : story
    if (activeStory && storyRef.current) {
      storyRef.current.focus()
    }
  }, [mode, soloStory, story])

  const updatePlayback = async (action: string) => {
    if (!ttsJobId) return
    try {
      const response = await fetch(`${API_BASE_URL}/v1/tts/jobs/${ttsJobId}:playback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      })
      if (!response.ok) throw new Error("Playback update failed.")
      const data = (await response.json()) as TTSStatusResponse
      setTtsStatus(data.status ?? ttsStatus)
      setTtsPlayback(data.playback_state ?? ttsPlayback)
      setTtsAudioUrl(normalizeAudioUrl(data.audio_url))
      setTtsError(data.error_message ?? null)
      setTtsFromCache(Boolean(data.from_cache))
    } catch {
      setTtsError("We couldn't sync the narration controls. Please try again.")
    }
  }

  const requestShare = async () => {
    if (!multiplayerSession) return
    try {
      if (shareUrl) {
        if (navigator?.clipboard?.writeText) {
          await navigator.clipboard.writeText(shareUrl)
        }
        return
      }
      const hostToken = multiplayerSession.hostToken
      if (!hostToken) {
        setShareStatus("error")
        setShareError("Missing host token. Please return to the lobby and create a new room.")
        return
      }
      setShareStatus("loading")
      setShareError(null)
      const response = await fetch(
        `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/rounds/${multiplayerSession.roundId}:share`,
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
      if (!response.ok) throw new Error("Unable to generate a share link.")
      const data = (await response.json()) as ShareRoomResponse
      setShareUrl(data.share_url)
      setShareExpiresAt(data.expires_at)
      setShareStatus("ready")
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(data.share_url)
      }
    } catch (err) {
      setShareStatus("error")
      setShareError("We couldn't create a share link. Please try again.")
    }
  }

  const requestNarration = async () => {
    if (!multiplayerSession) return
    try {
      const hostToken = multiplayerSession.hostToken
      if (!hostToken) {
        setTtsStatus("error")
        setTtsError("Missing host token. Please return to the lobby and create a new room.")
        return
      }
      setTtsStatus("requesting")
      setTtsError(null)
      const response = await fetch(
        `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/rounds/${multiplayerSession.roundId}:tts`,
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
      if (response.status === 429) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail || "Narration requests are rate limited. Please wait.")
      }
      if (!response.ok) throw new Error("Unable to request narration.")
      const data = (await response.json()) as TTSStatusResponse
      setTtsJobId(data.job_id ?? null)
      setTtsStatus(data.status ?? "idle")
      setTtsPlayback(data.playback_state ?? "idle")
      setTtsAudioUrl(normalizeAudioUrl(data.audio_url))
      setTtsError(data.error_message ?? null)
      setTtsFromCache(Boolean(data.from_cache))
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to request narration."
      setTtsStatus("error")
      setTtsError(message)
    }
  }

  const requestSoloNarration = async () => {
    if (!soloSession || !soloStory) return
    try {
      setTtsStatus("requesting")
      setTtsError(null)
      const response = await fetch(`${API_BASE_URL}/v1/tts/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          story: soloStory,
          session_id: soloSession.roomId,
          round_id: soloSession.roundId,
        }),
      })
      if (response.status === 429) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail || "Narration requests are rate limited. Please wait.")
      }
      if (!response.ok) throw new Error("Unable to request narration.")
      const data = (await response.json()) as TTSStatusResponse
      setTtsJobId(data.job_id ?? null)
      setTtsStatus(data.status ?? "idle")
      setTtsPlayback(data.playback_state ?? "idle")
      setTtsAudioUrl(normalizeAudioUrl(data.audio_url))
      setTtsError(data.error_message ?? null)
      setTtsFromCache(Boolean(data.from_cache))
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to request narration."
      setTtsStatus("error")
      setTtsError(message)
    }
  }

  const ttsIsReady = ttsStatus === "ready" || ttsStatus === "from_cache"
  const ttsIsWorking = ["requesting", "queued", "generating"].includes(ttsStatus)
  const ttsIsBlocked = ttsStatus === "blocked"
  const ttsIsError = ttsStatus === "error"

  const handlePlay = async () => {
    if (!audioRef.current || !ttsAudioUrl) return
    try {
      await audioRef.current.play()
      setTtsPlayback("playing")
      await updatePlayback("play")
    } catch {
      setTtsError("Your browser blocked playback. Try again.")
    }
  }

  const handlePause = async () => {
    if (!audioRef.current) return
    audioRef.current.pause()
    setTtsPlayback("paused")
    await updatePlayback("pause")
  }

  const handleStop = async () => {
    if (!audioRef.current) return
    audioRef.current.pause()
    audioRef.current.currentTime = 0
    setTtsPlayback("stopped")
    await updatePlayback("stop")
  }

  if (mode === "none") {
    return (
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold">Reveal</h1>
        <p className="text-slate-600 dark:text-slate-300">
          No active session found. Start a new round to reveal a story.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/"
            className="btn-primary"
          >
            Return to Start
          </Link>
          <Link
            href="/room"
            className="btn-secondary"
          >
            Go to Room Lobby
          </Link>
        </div>
      </section>
    )
  }

  if (mode === "solo" && soloSession) {
    return (
      <section className="space-y-6">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold">Story Reveal</h1>
          <p className="text-slate-600 dark:text-slate-300">
            Your story is ready. Controls stay quiet so the story gets the spotlight.
          </p>
        </header>

        {!soloReady && (
          <div
            className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200"
            role="alert"
          >
            Finish your prompts before revealing the story.
          </div>
        )}

        {soloReady && soloStory && (
          <div
            className="story-stage text-xl leading-relaxed md:text-2xl"
            role="region"
            aria-label="Completed story"
            tabIndex={-1}
            ref={storyRef}
          >
            <div className="max-w-[70ch]">{soloStory}</div>
          </div>
        )}

        {soloReady && soloStory && (
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Story narration</h2>
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  Generate an AI narration of your story.
                </p>
              </div>
              {ttsIsReady && ttsAudioUrl && (
                <a
                  href={ttsAudioUrl}
                  download
                  className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
                >
                  Download audio
                </a>
              )}
            </div>

            <div
              className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-200"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              <p className="font-medium">{ttsStatusLabel(ttsStatus, ttsFromCache, ttsError)}</p>
              {ttsPlayback !== "idle" && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Playback: {ttsPlayback}
                </p>
              )}
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              {ttsStatus === "idle" && (
                <button
                  type="button"
                  onClick={requestSoloNarration}
                  className="btn-primary"
                >
                  <Volume2 className="mr-2 h-4 w-4" />
                  Generate narration
                </button>
              )}

              {ttsIsError && (
                <button
                  type="button"
                  onClick={requestSoloNarration}
                  className="btn-primary"
                >
                  <Volume2 className="mr-2 h-4 w-4" />
                  Retry narration
                </button>
              )}

              {ttsIsWorking && (
                <button
                  type="button"
                  disabled
                  className="btn-primary"
                >
                  Generating…
                </button>
              )}

              {ttsIsReady && (
                <>
                  <button
                    type="button"
                    onClick={handlePlay}
                    className="btn-primary"
                  >
                    <Play className="mr-2 h-4 w-4" />
                    {ttsPlayback === "paused" ? "Resume" : "Play"}
                  </button>
                  <button
                    type="button"
                    onClick={handlePause}
                    disabled={ttsPlayback !== "playing"}
                    className="btn-secondary"
                  >
                    <Pause className="mr-2 h-4 w-4" />
                    Pause
                  </button>
                  <button
                    type="button"
                    onClick={handleStop}
                    className="btn-secondary"
                  >
                    <Square className="mr-2 h-4 w-4" />
                    Stop
                  </button>
                </>
              )}
            </div>

            {ttsAudioUrl && (
              <audio
                ref={audioRef}
                preload="none"
                onEnded={() => {
                  setTtsPlayback("complete")
                  updatePlayback("complete")
                }}
                className="hidden"
              />
            )}
          </section>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              setTtsJobId(null)
              setTtsStatus("idle")
              setTtsPlayback("idle")
              setTtsAudioUrl(null)
              setTtsError(null)
              setTtsFromCache(false)
              const nextSession = restartSoloRound(soloSession)
              saveSoloSession(nextSession)
              setSoloSession(nextSession)
              router.push("/prompting")
            }}
            className="btn-primary"
          >
            Replay with New Prompts
          </button>
          <Link
            href="/"
            className="btn-secondary"
          >
            Back to Start
          </Link>
        </div>
      </section>
    )
  }

  if (!multiplayerSession) {
    return null
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Story Reveal</h1>
        <p className="text-slate-600 dark:text-slate-300">
          The host reveals the story for everyone. Once revealed, it stays locked for this round.
        </p>
      </header>

      {error && (
        <div
          className="flex items-start gap-3 rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          role="alert"
        >
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="rounded-xl border bg-card p-5 text-sm text-muted-foreground shadow-sm">
        Room: <span className="mono-chip">{multiplayerSession.roomCode}</span>
        {" · "}
        Round {roundIndex + 1}
      </div>

      {story ? (
        <div
          className="story-stage text-xl leading-relaxed md:text-2xl"
          role="region"
          aria-label="Completed story"
          tabIndex={-1}
          ref={storyRef}
        >
          <div className="max-w-[70ch]">{story}</div>
        </div>
      ) : (
        <div
          className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {!isHost
            ? "Waiting for the host to reveal the story."
            : readyToReveal
              ? "All prompts are in. You're ready to reveal."
              : "Ready to reveal once everyone has submitted."}
        </div>
      )}

      {story && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Story narration</h2>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Optional narration generated after reveal. Everyone can listen once it’s ready.
              </p>
            </div>
            {ttsIsReady && ttsAudioUrl && (
              <a
                href={ttsAudioUrl}
                download
                className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
              >
                Download audio
              </a>
            )}
          </div>

          <div
            className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-200"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            <p className="font-medium">{ttsStatusLabel(ttsStatus, ttsFromCache, ttsError)}</p>
            {ttsPlayback !== "idle" && (
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Playback: {ttsPlayback}
              </p>
            )}
            {ttsIsBlocked && (
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Start a new round to try narration again.
              </p>
            )}
            {!isHost && ttsStatus === "idle" && (
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                The host can start narration when they’re ready.
              </p>
            )}
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            {isHost && ttsStatus === "idle" && (
              <button
                type="button"
                onClick={requestNarration}
                className="btn-primary"
              >
                <Volume2 className="mr-2 h-4 w-4" />
                Generate narration
              </button>
            )}

            {isHost && ttsIsError && (
              <button
                type="button"
                onClick={requestNarration}
                className="btn-primary"
              >
                <Volume2 className="mr-2 h-4 w-4" />
                Retry narration
              </button>
            )}

            {ttsIsWorking && (
              <button
                type="button"
                disabled
                className="btn-primary"
              >
                Generating…
              </button>
            )}

            {ttsIsReady && (
              <>
                <button
                  type="button"
                  onClick={handlePlay}
                  className="btn-primary"
                >
                  <Play className="mr-2 h-4 w-4" />
                  {ttsPlayback === "paused" ? "Resume" : "Play"}
                </button>
                <button
                  type="button"
                  onClick={handlePause}
                  disabled={ttsPlayback !== "playing"}
                  className="btn-secondary"
                >
                  <Pause className="mr-2 h-4 w-4" />
                  Pause
                </button>
                <button
                  type="button"
                  onClick={handleStop}
                  className="btn-secondary"
                >
                  <Square className="mr-2 h-4 w-4" />
                  Stop
                </button>
              </>
            )}
          </div>

          {ttsAudioUrl && (
            <audio
              ref={audioRef}
              preload="none"
              onEnded={() => {
                setTtsPlayback("complete")
                updatePlayback("complete")
              }}
              className="hidden"
            />
          )}
        </section>
      )}

      {story && isHost && (
        <section className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Share the story</h2>
              <p className="text-sm text-muted-foreground">
                Generate a public link that shows the rendered story only.
              </p>
            </div>
            <button
              type="button"
              onClick={requestShare}
              className="btn-outline"
            >
              <Share2 className="mr-2 h-4 w-4" />
              {shareStatus === "loading" ? "Creating..." : shareUrl ? "Copy share link" : "Create share link"}
            </button>
          </div>

          {shareError && (
            <div
              className="mt-4 flex items-start gap-3 rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
              role="alert"
            >
              <AlertTriangle className="h-5 w-5 shrink-0" />
              <span>{shareError}</span>
            </div>
          )}

          {shareUrl && (
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/40">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                Share link
              </p>
              <p className="mt-2 break-all font-semibold text-slate-900 dark:text-slate-100">{shareUrl}</p>
              {shareExpiresAt && (
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  Expires on {new Date(shareExpiresAt).toLocaleString()}.
                </p>
              )}
            </div>
          )}
        </section>
      )}

      <div className="flex flex-wrap gap-3">
        {isHost && !story && (
          <button
            type="button"
            onClick={async () => {
              if (!multiplayerSession) return
              const hostToken = multiplayerSession.hostToken
              if (!hostToken) {
                setError("Missing host token. Please return to the lobby and create a new room.")
                return
              }
              try {
                setError(null)
                const response = await fetch(
                  `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/reveal`,
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
                if (response.status === 409) {
                  const payload = (await response.json()) as { detail?: string }
                  throw new Error(payload.detail || "Waiting for all prompts.")
                }
                if (!response.ok) throw new Error("Unable to reveal the story.")
                const data = (await response.json()) as RevealRoomResponse
                setStory(data.rendered_story)
              } catch (err) {
                const message = err instanceof Error ? err.message : "Unable to reveal the story."
                setError(message)
              }
            }}
            disabled={!readyToReveal}
            className="btn-primary"
          >
            <Sparkles className="mr-2 h-4 w-4" />
            Reveal Story
          </button>
        )}

        {isHost && story && (
          <button
            type="button"
            onClick={async () => {
              try {
                const hostToken = multiplayerSession.hostToken
                if (!hostToken) {
                  setError("Missing host token. Please return to the lobby and create a new room.")
                  return
                }
                const response = await fetch(
                  `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/replay`,
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
                if (!response.ok) throw new Error("Unable to replay this round.")
                const data = (await response.json()) as ReplayRoomResponse
                const nextSession = { ...multiplayerSession, roundId: data.round_id }
                saveMultiplayerSession(nextSession)
                setMultiplayerSession(nextSession)
                router.push("/prompting")
              } catch (err) {
                const message = err instanceof Error ? err.message : "Unable to replay this round."
                setError(message)
              }
            }}
            className={ttsIsBlocked ? "btn-primary" : "btn-secondary"}
          >
            Replay Same Template
          </button>
        )}

        <Link
          href="/lobby"
          className="btn-secondary"
        >
          Back to Lobby
        </Link>
      </div>
    </section>
  )
}
