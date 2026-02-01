"use client"

import { useTheme } from "next-themes"
import { useSyncExternalStore } from "react"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const isClient = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  )

  if (!isClient) return null

  const isDark = theme === "dark"

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="rounded border border-slate-300 px-3 py-1 text-sm dark:border-slate-700"
      aria-label="Toggle theme"
    >
      {isDark ? "Light mode" : "Dark mode"}
    </button>
  )
}
