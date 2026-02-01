"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import type { SoloSession } from "@/lib/solo-session"
import { loadSoloSession, restartSoloRound, saveSoloSession } from "@/lib/solo-session"
import type { MultiplayerSession } from "@/lib/multiplayer-session"
import {
  clearMultiplayerSession,
  loadMultiplayerSession,
  saveMultiplayerSession,
} from "@/lib/multiplayer-session"
import { renderStory } from "@/lib/story-renderer"

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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

export default function RevealClient() {
  const router = useRouter()
  const storyRef = useRef<HTMLDivElement | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const reconnectRef = useRef<string | null>(null)
  const [soloSession, setSoloSession] = useState<SoloSession | null>(null)
  const [multiplayerSession, setMultiplayerSession] = useState<MultiplayerSession | null>(null)
  const [story, setStory] = useState<string | null>(null)
  const [status, setStatus] = useState<"idle" | "loading" | "waiting" | "ready" | "error">("idle")
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

  useEffect(() => {
    setSoloSession(loadSoloSession())
    setMultiplayerSession(loadMultiplayerSession())
  }, [])

  useEffect(() => {
    if (!multiplayerSession || multiplayerSession.playerId === "host") return

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
  }, [multiplayerSession])

  useEffect(() => {
    if (!multiplayerSession) return
    setShareStatus("idle")
    setShareUrl(null)
    setShareExpiresAt(null)
    setShareError(null)
  }, [multiplayerSession?.roundId])

  const mode = useMemo(() => {
    if (soloSession) return "solo"
    if (multiplayerSession) return "multi"
    return "none"
  }, [soloSession, multiplayerSession])

  const isHost = useMemo(
    () => multiplayerSession?.playerId === "host",
    [multiplayerSession]
  )

  const soloReady = useMemo(() => {
    return soloSession?.prompts.every((prompt) => prompt.value && prompt.value.trim()) ?? false
  }, [soloSession])

  const soloStory = useMemo(() => {
    if (!soloSession || !soloReady) return null
    return renderStory(soloSession.templateId, soloSession.prompts)
  }, [soloSession, soloReady])

  const normalizeAudioUrl = (url: string | null | undefined) => {
    if (!url) return null
    if (url.startsWith("http://") || url.startsWith("https://")) return url
    if (url.startsWith("/")) {
      if (typeof window !== "undefined") return `${window.location.origin}${url}`
      return url
    }
    return `${API_BASE_URL}/${url}`
  }

  useEffect(() => {
    if (mode !== "multi" || !multiplayerSession) return

    let active = true
    let timer: ReturnType<typeof setInterval> | null = null

    const loadStory = async () => {
      try {
        if (!active) return
        setStatus((prev) => (prev === "ready" ? "ready" : "loading"))
        const response = await fetch(
          `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/rounds/${multiplayerSession.roundId}/story`
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (response.status === 409) {
          if (!active) return
          setStatus("waiting")
          return
        }
        if (!response.ok) throw new Error("Unable to load story.")
        const data = (await response.json()) as StoryResponse
        if (!active) return
        setStory(data.rendered_story)
        setStatus("ready")
        setError(null)
      } catch (err) {
        if (!active) return
        setStatus("error")
        setError("We couldn't load the story yet. Please try again.")
      }
    }

    loadStory()

    if (!isHost) {
      timer = setInterval(loadStory, 3000)
    }

    return () => {
      active = false
      if (timer) clearInterval(timer)
    }
  }, [mode, multiplayerSession, isHost])

  useEffect(() => {
    if (mode !== "multi" || !multiplayerSession || !isHost || story) return

    let active = true
    let timer: ReturnType<typeof setInterval> | null = null

    const loadProgress = async () => {
      try {
        if (!active) return
        const response = await fetch(
          `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/rounds/${multiplayerSession.roundId}/progress`
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (!response.ok) throw new Error("Unable to load progress.")
        const data = (await response.json()) as RoomProgressResponse
        if (!active) return
        setReadyToReveal(data.ready_to_reveal)
      } catch {
        if (!active) return
        setReadyToReveal(false)
      }
    }

    loadProgress()
    timer = setInterval(loadProgress, 3000)

    return () => {
      active = false
      if (timer) clearInterval(timer)
    }
  }, [mode, multiplayerSession, isHost, story])

  useEffect(() => {
    if (mode !== "multi" || !multiplayerSession || !story) {
      setTtsJobId(null)
      setTtsStatus("idle")
      setTtsPlayback("idle")
      setTtsAudioUrl(null)
      setTtsError(null)
      setTtsFromCache(false)
      return
    }

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
  }, [mode, multiplayerSession, story])

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
      setShareStatus("loading")
      setShareError(null)
      const response = await fetch(
        `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/rounds/${multiplayerSession.roundId}:share`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host_token: multiplayerSession.playerToken }),
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
      setTtsStatus("requesting")
      setTtsError(null)
      const response = await fetch(
        `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/rounds/${multiplayerSession.roundId}:tts`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host_token: multiplayerSession.playerToken }),
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

  const ttsIsReady = ttsStatus === "ready" || ttsStatus === "from_cache"
  const ttsIsWorking = ["requesting", "queued", "generating"].includes(ttsStatus)
  const ttsIsBlocked = ttsStatus === "blocked"
  const ttsIsError = ttsStatus === "error"

  const ttsStatusLabel = () => {
    if (ttsIsBlocked) return ttsError || "Narration is disabled for this round."
    if (ttsIsError) return ttsError || "Narration failed. Try again."
    if (ttsIsWorking) return "Generating narration..."
    if (ttsIsReady) return ttsFromCache ? "Narration ready (cached)." : "Narration ready."
    return "Narration hasn’t been requested yet."
  }

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
            href="/mode"
            className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
          >
            Go to Mode Select
          </Link>
          <Link
            href="/room"
            className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
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
            className="rounded-2xl border border-slate-200 bg-white p-6 text-lg leading-relaxed shadow-sm dark:border-slate-800 dark:bg-slate-950"
            role="region"
            aria-label="Completed story"
            tabIndex={-1}
            ref={storyRef}
          >
            {soloStory}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              const nextSession = restartSoloRound(soloSession)
              saveSoloSession(nextSession)
              setSoloSession(nextSession)
              router.push("/prompting")
            }}
            className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
          >
            Replay with New Prompts
          </button>
          <Link
            href="/mode"
            className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
          >
            Back to Mode Select
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
          className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
        Room: <span className="font-semibold text-slate-900 dark:text-slate-100">{multiplayerSession.roomCode}</span>
        {" · "}
        Round: <span className="font-semibold text-slate-900 dark:text-slate-100">{multiplayerSession.roundId}</span>
      </div>

      {story ? (
        <div
          className="rounded-2xl border border-slate-200 bg-white p-6 text-lg leading-relaxed shadow-sm dark:border-slate-800 dark:bg-slate-950"
          role="region"
          aria-label="Completed story"
          tabIndex={-1}
          ref={storyRef}
        >
          {story}
        </div>
      ) : (
        <div
          className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {status === "waiting" || !isHost
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
            <p className="font-medium">{ttsStatusLabel()}</p>
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
                className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
              >
                Generate narration
              </button>
            )}

            {isHost && ttsIsError && (
              <button
                type="button"
                onClick={requestNarration}
                className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
              >
                Retry narration
              </button>
            )}

            {ttsIsWorking && (
              <button
                type="button"
                disabled
                className="cursor-not-allowed rounded-full bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400"
              >
                Generating…
              </button>
            )}

            {ttsIsReady && (
              <>
                <button
                  type="button"
                  onClick={handlePlay}
                  className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
                >
                  {ttsPlayback === "paused" ? "Resume" : "Play"}
                </button>
                <button
                  type="button"
                  onClick={handlePause}
                  disabled={ttsPlayback !== "playing"}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    ttsPlayback === "playing"
                      ? "border border-slate-300 text-slate-700 hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
                      : "cursor-not-allowed border border-slate-200 text-slate-400 dark:border-slate-800 dark:text-slate-500"
                  }`}
                >
                  Pause
                </button>
                <button
                  type="button"
                  onClick={handleStop}
                  className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
                >
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
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Share the story</h2>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Generate a public link that shows the rendered story only.
              </p>
            </div>
            <button
              type="button"
              onClick={requestShare}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
            >
              {shareStatus === "loading" ? "Creating..." : shareUrl ? "Copy share link" : "Create share link"}
            </button>
          </div>

          {shareError && (
            <div
              className="mt-4 rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
              role="alert"
            >
              {shareError}
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
              try {
                setStatus("loading")
                setError(null)
                const response = await fetch(
                  `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/reveal`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ host_token: multiplayerSession.playerToken }),
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
                setStatus("ready")
              } catch (err) {
                const message = err instanceof Error ? err.message : "Unable to reveal the story."
                setError(message)
                setStatus("error")
              }
            }}
            disabled={!readyToReveal}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              readyToReveal
                ? "bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
                : "cursor-not-allowed bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
            }`}
          >
            Reveal Story
          </button>
        )}

        {isHost && story && (
          <button
            type="button"
            onClick={async () => {
              try {
                const response = await fetch(
                  `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}/replay`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ host_token: multiplayerSession.playerToken }),
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
            className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
          >
            Replay Same Template
          </button>
        )}

        <Link
          href="/room"
          className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
        >
          Back to Lobby
        </Link>
      </div>
    </section>
  )
}
