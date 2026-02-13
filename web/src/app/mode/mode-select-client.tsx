"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { AlertTriangle } from "lucide-react"

import { createSoloSession, saveSoloSession } from "@/lib/solo-session"

const TEMPLATE_STORAGE_KEY = "storyfill.templateId"

export default function ModeSelectClient() {
  const router = useRouter()
  const [templateId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return window.localStorage.getItem(TEMPLATE_STORAGE_KEY)
  })
  const [error, setError] = useState<string | null>(null)

  const hasTemplate = Boolean(templateId)

  async function handleSoloStart() {
    if (!templateId) return
    setError(null)
    try {
      const session = await createSoloSession(templateId)
      saveSoloSession(session)
      router.push("/prompting")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to load template."
      setError(message)
    }
  }

  function handleMultiplayerStart() {
    router.push("/room")
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Choose a Mode</h1>
        <p className="text-muted-foreground">
          Decide how you want to play. Solo skips the lobby and jumps right into prompts.
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

      {!hasTemplate && (
        <div
          className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200"
          role="status"
          aria-live="polite"
        >
          No template selected yet. Head back to Templates if you want a different story.
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <button
          type="button"
          onClick={handleSoloStart}
          className="focus-ring flex h-full flex-col gap-3 rounded-xl border bg-card p-5 text-left shadow-sm transition hover:border-ring"
        >
          <div className="space-y-1">
            <p className="text-lg font-semibold">Solo</p>
            <p className="text-sm text-muted-foreground">
              Instant prompts, no lobby, and a single-player flow.
            </p>
          </div>
          <span className="text-sm text-muted-foreground">
            A room and round are created automatically for you.
          </span>
        </button>

        <button
          type="button"
          onClick={handleMultiplayerStart}
          className="focus-ring flex h-full flex-col gap-3 rounded-xl border bg-card p-5 text-left shadow-sm transition hover:border-ring"
        >
          <div className="space-y-1">
            <p className="text-lg font-semibold">Multiplayer</p>
            <p className="text-sm text-muted-foreground">
              Create a lobby, invite friends, and play together.
            </p>
          </div>
          <span className="text-sm text-muted-foreground">
            You’ll head to the lobby to start a room.
          </span>
        </button>
      </div>
    </section>
  )
}
