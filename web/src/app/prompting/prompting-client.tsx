"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import type { SoloSession } from "@/lib/solo-session"
import { loadSoloSession, restartSoloRound, saveSoloSession } from "@/lib/solo-session"
import { clearMultiplayerSession, loadMultiplayerSession, saveMultiplayerSession } from "@/lib/multiplayer-session"
import { getPromptIssue, isReadable, promptLimits } from "@/lib/prompt-validation"

type MultiplayerPrompt = {
  id: string
  label: string
  type: string
  submitted: boolean
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
  prompts: MultiplayerPrompt[]
}

export default function PromptingClient() {
  const router = useRouter()
  const [session, setSession] = useState<SoloSession | null>(null)
  const [multiplayerPrompts, setMultiplayerPrompts] = useState<MultiplayerPrompt[]>([])
  const [multiplayerStatus, setMultiplayerStatus] = useState<"idle" | "loading" | "ready" | "error">("idle")
  const [multiplayerError, setMultiplayerError] = useState<string | null>(null)
  const [multiplayerAnswers, setMultiplayerAnswers] = useState<Record<string, string>>({})
  const [multiplayerSubmitStatus, setMultiplayerSubmitStatus] = useState<"idle" | "submitting" | "done">("idle")
  const [multiplayerValidation, setMultiplayerValidation] = useState(false)
  const [soloAnswers, setSoloAnswers] = useState<Record<string, string>>({})
  const [soloError, setSoloError] = useState<string | null>(null)
  const [soloValidation, setSoloValidation] = useState(false)

  useEffect(() => {
    setSession(loadSoloSession())
  }, [])

  const soloReady =
    session?.prompts.every((prompt) => isReadable(soloAnswers[prompt.id] ?? "", prompt.type)) ?? false

  useEffect(() => {
    const multiplayer = loadMultiplayerSession()
    if (!multiplayer || session) return

    let active = true
    async function loadPrompts() {
      try {
        setMultiplayerStatus("loading")
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
        let nextSession = multiplayer
        let reconciledPrompts: MultiplayerPrompt[] | null = null

        if (multiplayer.role !== "host") {
          const reconnectResponse = await fetch(
            `${apiBase}/v1/rooms/${multiplayer.roomCode}/players/${multiplayer.playerId}:reconnect`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ player_token: multiplayer.playerToken }),
            }
          )
          if (reconnectResponse.status === 410) {
            router.push("/expired")
            return
          }
          if (!reconnectResponse.ok) {
            clearMultiplayerSession()
            throw new Error("Unable to restore your session. Please rejoin the room.")
          }
          const reconnectData = (await reconnectResponse.json()) as ReconnectPlayerResponse
          reconciledPrompts = reconnectData.prompts
          nextSession = {
            ...multiplayer,
            roomCode: reconnectData.room_snapshot.room_code,
            roomId: reconnectData.room_snapshot.room_id,
            roundId: reconnectData.room_snapshot.round_id,
            templateId: reconnectData.room_snapshot.template_id ?? null,
            playerId: reconnectData.player_id,
            playerToken: reconnectData.player_token,
            displayName: reconnectData.player_display_name ?? multiplayer.displayName ?? null,
          }
          saveMultiplayerSession(nextSession)
        }

        if (reconciledPrompts) {
          if (!active) return
          setMultiplayerPrompts(reconciledPrompts)
          setMultiplayerStatus("ready")
          return
        }

        const response = await fetch(
          `${apiBase}/v1/rooms/${nextSession.roomCode}/rounds/${nextSession.roundId}/prompts?player_id=${nextSession.playerId}&player_token=${encodeURIComponent(nextSession.playerToken)}`
        )
        if (response.status === 410) {
          router.push("/expired")
          return
        }
        if (response.status === 409) {
          // State-machine guard: multiplayer prompt collection hasn't started yet.
          router.push("/lobby")
          return
        }
        if (!response.ok) throw new Error("Failed to load prompts.")
        const data = (await response.json()) as { prompts: MultiplayerPrompt[] }
        if (!active) return
        setMultiplayerPrompts(data.prompts)
        setMultiplayerStatus("ready")
      } catch (err) {
        if (!active) return
        setMultiplayerStatus("error")
        const message =
          err instanceof Error ? err.message : "Unable to load prompts. Please try again."
        setMultiplayerError(message)
      }
    }
    loadPrompts()

    return () => {
      active = false
    }
  }, [session, router])

  if (!session) {
    const multiplayer = loadMultiplayerSession()
    if (multiplayer) {
      return (
        <section className="space-y-6">
          <header className="space-y-2">
            <h1 className="text-2xl font-semibold">Your Prompts</h1>
            <p className="text-slate-600 dark:text-slate-300">
              Multiplayer prompts are blind — only the labels are shown.
            </p>
          </header>

          {multiplayerStatus === "loading" && (
            <div className="rounded-lg border border-dashed border-slate-300 p-6 text-slate-600 dark:border-slate-700 dark:text-slate-300">
              Assigning prompts...
            </div>
          )}

          {multiplayerStatus === "error" && multiplayerError && (
            <div
              className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
              role="alert"
            >
              {multiplayerError}
            </div>
          )}

          {multiplayerStatus === "ready" && (
            <div className="grid gap-4 md:grid-cols-2">
              {multiplayerPrompts.map((prompt) => (
                <label
                  key={prompt.id}
                  className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950"
                >
                  <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                    {prompt.type}
                  </span>
                  <span className="text-base font-semibold">{prompt.label}</span>
                  <input
                    type="text"
                    placeholder="Type your answer"
                    value={multiplayerAnswers[prompt.id] ?? ""}
                    maxLength={promptLimits(prompt.type).max}
                    onChange={(event) =>
                      setMultiplayerAnswers((prev) => ({ ...prev, [prompt.id]: event.target.value }))
                    }
                    aria-invalid={
                      multiplayerValidation &&
                      !!getPromptIssue(multiplayerAnswers[prompt.id] ?? "", prompt.type)
                    }
                    className={`rounded-lg border px-3 py-2 text-sm focus:border-slate-400 dark:bg-slate-950 ${
                      multiplayerValidation &&
                      getPromptIssue(multiplayerAnswers[prompt.id] ?? "", prompt.type)
                        ? "border-rose-400 focus:border-rose-400 dark:border-rose-700"
                        : "border-slate-200 dark:border-slate-700"
                    }`}
                  />
                  {multiplayerValidation &&
                    getPromptIssue(multiplayerAnswers[prompt.id] ?? "", prompt.type) && (
                      <span className="text-xs text-rose-600 dark:text-rose-300">
                        {getPromptIssue(multiplayerAnswers[prompt.id] ?? "", prompt.type)}
                      </span>
                    )}
                </label>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={async () => {
              const multiplayer = loadMultiplayerSession()
              if (!multiplayer) return
              try {
                setMultiplayerError(null)
                setMultiplayerValidation(true)
                const invalidPrompt = multiplayerPrompts.find((prompt) =>
                  getPromptIssue(multiplayerAnswers[prompt.id] ?? "", prompt.type)
                )
                if (invalidPrompt) {
                  const issue = getPromptIssue(
                    multiplayerAnswers[invalidPrompt.id] ?? "",
                    invalidPrompt.type
                  )
                  setMultiplayerError(`One of your prompts needs attention. ${issue}`)
                  setMultiplayerSubmitStatus("idle")
                  return
                }
                setMultiplayerSubmitStatus("submitting")
                const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
                for (const prompt of multiplayerPrompts) {
                  const response = await fetch(
                    `${apiBase}/v1/rooms/${multiplayer.roomCode}/rounds/${multiplayer.roundId}/prompts/${prompt.id}:submit`,
                    {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        player_id: multiplayer.playerId,
                        player_token: multiplayer.playerToken,
                        value: multiplayerAnswers[prompt.id] ?? "",
                      }),
                    }
                  )
                  if (response.status === 410) {
                    router.push("/expired")
                    return
                  }
                  if (!response.ok) {
                    const payload = (await response.json()) as { detail?: string }
                    if (response.status === 429) {
                      throw new Error(payload.detail || "You're submitting too quickly. Please wait.")
                    }
                    throw new Error(payload.detail || "Unable to submit prompts.")
                  }
                }
                setMultiplayerSubmitStatus("done")
                router.push("/waiting")
              } catch (err) {
                const message = err instanceof Error ? err.message : "Unable to submit prompts. Please try again."
                setMultiplayerError(message)
                setMultiplayerSubmitStatus("idle")
              }
            }}
            className="btn-primary"
          >
            {multiplayerSubmitStatus === "submitting" ? "Submitting..." : "Submit Prompts"}
          </button>
        </section>
      )
    }

    return (
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold">Prompting</h1>
        <p className="text-slate-600 dark:text-slate-300">
          No active solo session found. Choose a mode to begin.
        </p>
        <Link
          href="/"
          className="btn-primary"
        >
          Return to Start
        </Link>
      </section>
    )
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Your Prompts</h1>
        <p className="text-slate-600 dark:text-slate-300">
          Solo play skips the lobby — your prompts are assigned immediately.
        </p>
      </header>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-300">
        Room: <span className="font-semibold text-slate-900 dark:text-slate-100">{session.roomId}</span>
        {" · "}
        Round: <span className="font-semibold text-slate-900 dark:text-slate-100">{session.roundId}</span>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {session.prompts.map((prompt) => (
          <label
            key={prompt.id}
            className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950"
          >
            <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">
              {prompt.type}
            </span>
            <span className="text-base font-semibold">{prompt.label}</span>
            <input
              type="text"
              placeholder="Type your answer"
              value={soloAnswers[prompt.id] ?? ""}
              maxLength={promptLimits(prompt.type).max}
              onChange={(event) =>
                setSoloAnswers((prev) => ({ ...prev, [prompt.id]: event.target.value }))
              }
              aria-invalid={soloValidation && !!getPromptIssue(soloAnswers[prompt.id] ?? "", prompt.type)}
              className={`rounded-lg border px-3 py-2 text-sm focus:border-slate-400 dark:bg-slate-950 ${
                soloValidation && getPromptIssue(soloAnswers[prompt.id] ?? "", prompt.type)
                  ? "border-rose-400 focus:border-rose-400 dark:border-rose-700"
                  : "border-slate-200 dark:border-slate-700"
              }`}
            />
            {soloValidation && getPromptIssue(soloAnswers[prompt.id] ?? "", prompt.type) && (
              <span className="text-xs text-rose-600 dark:text-rose-300">
                {getPromptIssue(soloAnswers[prompt.id] ?? "", prompt.type)}
              </span>
            )}
          </label>
        ))}
      </div>

      {soloError && (
        <div
          className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          role="alert"
        >
          {soloError}
        </div>
      )}

      <button
        type="button"
        onClick={() => {
          setSoloError(null)
          setSoloValidation(true)
          const invalidPrompt = session.prompts.find(
            (prompt) => !!getPromptIssue(soloAnswers[prompt.id] ?? "", prompt.type)
          )
          if (invalidPrompt) {
            const issue = getPromptIssue(soloAnswers[invalidPrompt.id] ?? "", invalidPrompt.type)
            setSoloError(issue || "Please update the highlighted prompt.")
            return
          }
          const updatedSession = {
            ...session,
            prompts: session.prompts.map((prompt) => ({
              ...prompt,
              value: soloAnswers[prompt.id] ?? "",
            })),
          }
          saveSoloSession(updatedSession)
          setSession(updatedSession)
          router.push("/reveal")
        }}
        disabled={!soloReady}
        className="btn-primary"
      >
        Submit Prompts
      </button>

      <button
        type="button"
        onClick={() => {
          const nextSession = restartSoloRound(session)
          saveSoloSession(nextSession)
          setSession(nextSession)
        }}
        className="btn-secondary"
      >
        Replay Solo Round
      </button>
    </section>
  )
}
