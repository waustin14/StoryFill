"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"

import type { MultiplayerSession } from "@/lib/multiplayer-session"
import { clearMultiplayerSession, loadMultiplayerSession, saveMultiplayerSession } from "@/lib/multiplayer-session"
import { createSoloSession, saveSoloSession } from "@/lib/solo-session"

type TemplateSummary = {
  id: string
  title: string
  genre: string
  content_rating: string
  description: string
}

const STORAGE_KEY = "storyfill.templateId"
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

export default function TemplateSelectClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const forcedMode = searchParams.get("mode")
  const [templates, setTemplates] = useState<TemplateSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading")
  const [submitStatus, setSubmitStatus] = useState<"idle" | "saving" | "error">("idle")
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [multiplayerSession, setMultiplayerSession] = useState<MultiplayerSession | null>(null)
  const [forceSolo, setForceSolo] = useState(false)

  const soloOverride = forceSolo || forcedMode === "solo"
  const isMultiplayer = Boolean(multiplayerSession) && !soloOverride
  const isHost = multiplayerSession?.role === "host"
  const selectionLocked = isMultiplayer && !isHost

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    const session = loadMultiplayerSession()
    if (soloOverride) {
      if (session) clearMultiplayerSession()
      setMultiplayerSession(null)
    } else {
      setMultiplayerSession(session)
    }
    if (session?.templateId) {
      setSelectedId(session.templateId)
    } else if (stored) {
      setSelectedId(stored)
    }
  }, [soloOverride])

  useEffect(() => {
    let active = true
    const controller = new AbortController()

    async function loadTemplates() {
      try {
        setStatus("loading")
        const response = await fetch(`${API_BASE_URL}/v1/templates`, {
          signal: controller.signal,
        })
        if (!response.ok) {
          throw new Error(`Template fetch failed: ${response.status}`)
        }
        const data = (await response.json()) as TemplateSummary[]
        if (!active) return
        setTemplates(data)
        setStatus("ready")
      } catch (error) {
        if (!active) return
        setStatus("error")
      }
    }

    loadTemplates()

    return () => {
      active = false
      controller.abort()
    }
  }, [])

  const selectionLabel = useMemo(() => {
    const match = templates.find((template) => template.id === selectedId)
    if (match) return match.title
    if (selectionLocked) return "Awaiting host selection"
    return "None selected"
  }, [selectedId, selectionLocked, templates])

  function handleSelection(id: string) {
    if (selectionLocked) return
    setSelectedId(id)
    window.localStorage.setItem(STORAGE_KEY, id)
  }

  async function handleContinue() {
    if (!selectedId) return
    setSubmitError(null)

    if (isMultiplayer) {
      if (!multiplayerSession) return
      if (isHost) {
        if (!multiplayerSession.hostToken) {
          setSubmitStatus("error")
          setSubmitError("Missing host credentials. Please recreate the room.")
          return
        }
        setSubmitStatus("saving")
        try {
          const response = await fetch(
            `${API_BASE_URL}/v1/rooms/${multiplayerSession.roomCode}:template`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                host_token: multiplayerSession.hostToken,
                template_id: selectedId,
              }),
            }
          )
          if (response.status === 410) {
            clearMultiplayerSession()
            router.push("/expired")
            return
          }
          if (!response.ok) {
            const payload = (await response.json()) as { detail?: string }
            throw new Error(payload.detail || "Unable to set the template.")
          }
          const data = (await response.json()) as { template_id: string }
          const nextSession = {
            ...multiplayerSession,
            templateId: data.template_id ?? selectedId,
          }
          saveMultiplayerSession(nextSession)
          setMultiplayerSession(nextSession)
          setSubmitStatus("idle")
        } catch (error) {
          const message = error instanceof Error ? error.message : "Unable to set the template."
          setSubmitStatus("error")
          setSubmitError(message)
          return
        }
      }
      router.push("/lobby")
      return
    }

    setSubmitStatus("saving")
    try {
      const soloSession = await createSoloSession(selectedId)
      saveSoloSession(soloSession)
      router.push("/prompting")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to load template."
      setSubmitStatus("error")
      setSubmitError(message)
    }
  }

  const canContinue = selectionLocked ? true : Boolean(selectedId)
  const continueLabel = isMultiplayer
    ? isHost
      ? submitStatus === "saving"
        ? "Saving..."
        : "Continue to Lobby"
      : "Head to Lobby"
    : "Start Solo"

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Choose a Story Template</h1>
        <p className="text-muted-foreground">
          {isMultiplayer
            ? "The host selects the template before the game starts."
            : "Pick one curated template to start. Your selection will carry forward."}
        </p>
      </header>

      {selectionLocked && (
        <div
          className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-300"
          role="status"
          aria-live="polite"
        >
          <p>You joined as a player. The host will confirm the template selection.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                clearMultiplayerSession()
                setMultiplayerSession(null)
                setForceSolo(true)
              }}
              className="btn-secondary"
            >
              Switch to Solo
            </button>
            <button
              type="button"
              onClick={() => router.push("/lobby")}
              className="btn-outline"
            >
              Back to Lobby
            </button>
          </div>
        </div>
      )}

      {submitError && (
        <div
          className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          role="alert"
        >
          {submitError}
        </div>
      )}

      {status === "loading" && (
        <div
          className="rounded-lg border border-dashed border-slate-300 p-6 text-slate-600 dark:border-slate-700 dark:text-slate-300"
          role="status"
          aria-live="polite"
        >
          Loading templates…
        </div>
      )}

      {status === "error" && (
        <div
          className="rounded-lg border border-rose-300 bg-rose-50 p-6 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          role="alert"
        >
          We couldn’t load templates right now. Please refresh and try again.
        </div>
      )}

      {status === "ready" && (
        <fieldset className="space-y-4">
          <legend className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Template List
          </legend>
          <div className="grid gap-4 md:grid-cols-2">
            {templates.map((template) => {
              const isSelected = template.id === selectedId
              return (
                <label
                  key={template.id}
                  className={`flex cursor-pointer flex-col gap-3 rounded-xl border p-4 transition ${
                    isSelected
                      ? "border-slate-900 bg-slate-50 shadow-sm dark:border-slate-200 dark:bg-slate-900/60"
                      : "border-slate-200 bg-white hover:border-slate-400 dark:border-slate-800 dark:bg-slate-950"
                  } ${selectionLocked ? "cursor-not-allowed opacity-70" : ""}`}
                  aria-disabled={selectionLocked}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-semibold">{template.title}</p>
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        {template.genre} · {template.content_rating}
                      </p>
                    </div>
                    <input
                      type="radio"
                      name="template"
                      value={template.id}
                      checked={isSelected}
                      onChange={() => handleSelection(template.id)}
                      className="mt-1 h-4 w-4 accent-primary"
                      aria-label={`Select ${template.title}`}
                      disabled={selectionLocked}
                    />
                  </div>
                  <p className="text-sm text-slate-600 dark:text-slate-300">
                    {template.description}
                  </p>
                </label>
              )
            })}
          </div>
        </fieldset>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/40">
        <span className="text-slate-600 dark:text-slate-300">
          Current selection: <strong className="text-slate-900 dark:text-slate-100">{selectionLabel}</strong>
        </span>
        <button
          type="button"
          disabled={!canContinue || submitStatus === "saving"}
          onClick={handleContinue}
          className="btn-primary"
        >
          {continueLabel}
        </button>
      </div>
    </section>
  )
}
