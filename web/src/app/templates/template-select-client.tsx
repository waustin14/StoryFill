"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

type TemplateSummary = {
  id: string
  title: string
  genre: string
  content_rating: string
}

const STORAGE_KEY = "storyfill.templateId"
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

export default function TemplateSelectClient() {
  const router = useRouter()
  const [templates, setTemplates] = useState<TemplateSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading")

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored) setSelectedId(stored)
  }, [])

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
    return match ? match.title : "None selected"
  }, [selectedId, templates])

  function handleSelection(id: string) {
    setSelectedId(id)
    window.localStorage.setItem(STORAGE_KEY, id)
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Choose a Story Template</h1>
        <p className="text-slate-600 dark:text-slate-300">
          Pick one curated template to start. Your selection will carry forward.
        </p>
      </header>

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
            {templates.map((template) => (
              <label
                key={template.id}
                className={`flex cursor-pointer flex-col gap-3 rounded-xl border p-4 transition ${
                  template.id === selectedId
                    ? "border-slate-900 bg-slate-50 shadow-sm dark:border-slate-200 dark:bg-slate-900/60"
                    : "border-slate-200 bg-white hover:border-slate-400 dark:border-slate-800 dark:bg-slate-950"
                }`}
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
                    checked={template.id === selectedId}
                    onChange={() => handleSelection(template.id)}
                    className="mt-1 h-4 w-4 accent-slate-900 dark:accent-slate-100"
                    aria-label={`Select ${template.title}`}
                  />
                </div>
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  Curated story framework with fresh prompts and a ready-to-reveal ending.
                </p>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/40">
        <span className="text-slate-600 dark:text-slate-300">
          Current selection: <strong className="text-slate-900 dark:text-slate-100">{selectionLabel}</strong>
        </span>
        <button
          type="button"
          disabled={!selectedId}
          onClick={() => {
            if (selectedId) router.push("/mode")
          }}
          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
            selectedId
              ? "bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
              : "cursor-not-allowed bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
          }`}
        >
          Continue
        </button>
      </div>
    </section>
  )
}
