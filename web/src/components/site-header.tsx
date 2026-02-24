"use client"

import Link from "next/link"
import { ThemeToggle } from "@/components/theme-toggle"

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-6">
          <Link href="/" className="focus-ring rounded-sm">
            <span className="font-display text-2xl font-black tracking-tight text-foreground">
              Story<span className="text-primary">Fill</span>
            </span>
          </Link>
        </div>
        <ThemeToggle />
      </div>
    </header>
  )
}
