"use client"

import Link from "next/link"
import { ThemeToggle } from "@/components/theme-toggle"

const navItems = [
  { href: "/", label: "Landing" },
  { href: "/templates", label: "Templates" },
  { href: "/mode", label: "Mode" },
  { href: "/room", label: "Lobby" },
  { href: "/prompting", label: "Prompting" },
  { href: "/waiting", label: "Waiting" },
  { href: "/reveal", label: "Reveal" }
]

export function SiteHeader() {
  return (
    <header className="border-b border-slate-200 dark:border-slate-800">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-lg font-semibold">
            StoryFill
          </Link>
          <nav className="hidden gap-4 text-sm text-slate-600 md:flex dark:text-slate-300">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href} className="hover:text-slate-900 dark:hover:text-white">
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
        <ThemeToggle />
      </div>
    </header>
  )
}
