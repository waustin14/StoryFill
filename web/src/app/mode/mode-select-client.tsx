"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { createSoloSession, saveSoloSession } from "@/lib/solo-session"

const TEMPLATE_STORAGE_KEY = "storyfill.templateId"

export default function ModeSelectClient() {
  const router = useRouter()
  const [templateId, setTemplateId] = useState<string | null>(null)

  useEffect(() => {
    const stored = window.localStorage.getItem(TEMPLATE_STORAGE_KEY)
    if (stored) setTemplateId(stored)
  }, [])

  const hasTemplate = useMemo(() => Boolean(templateId), [templateId])

  function handleSoloStart() {
    const session = createSoloSession(templateId)
    saveSoloSession(session)
    router.push("/prompting")
  }

  function handleMultiplayerStart() {
    router.push("/room")
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Choose a Mode</h1>
        <p className="text-slate-600 dark:text-slate-300">
          Decide how you want to play. Solo skips the lobby and jumps right into prompts.
        </p>
      </header>

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
          className="flex h-full flex-col gap-3 rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-slate-400 dark:border-slate-800 dark:bg-slate-950"
        >
          <div className="space-y-1">
            <p className="text-lg font-semibold">Solo</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Instant prompts, no lobby, and a single-player flow.
            </p>
          </div>
          <span className="text-sm text-slate-600 dark:text-slate-300">
            A room and round are created automatically for you.
          </span>
        </button>

        <button
          type="button"
          onClick={handleMultiplayerStart}
          className="flex h-full flex-col gap-3 rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-slate-400 dark:border-slate-800 dark:bg-slate-950"
        >
          <div className="space-y-1">
            <p className="text-lg font-semibold">Multiplayer</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Create a lobby, invite friends, and play together.
            </p>
          </div>
          <span className="text-sm text-slate-600 dark:text-slate-300">
            You’ll head to the lobby to start a room.
          </span>
        </button>
      </div>
    </section>
  )
}
