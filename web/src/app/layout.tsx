import type { Metadata } from "next"
import "./globals.css"
import { ThemeProvider } from "@/components/theme-provider"
import { SiteHeader } from "@/components/site-header"

export const metadata: Metadata = {
  title: "StoryFill",
  description: "Collaborative story game"
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white dark:focus:bg-slate-100 dark:focus:text-slate-900"
          >
            Skip to main content
          </a>
          <SiteHeader />
          <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  )
}
