import Link from "next/link"

type ShareArtifactResponse = {
  share_token: string
  room_code: string
  round_id: string
  rendered_story: string
  expires_at: string
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

async function loadShare(token: string): Promise<ShareArtifactResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/shares/${token}`, { cache: "no-store" })
    if (!response.ok) return null
    return (await response.json()) as ShareArtifactResponse
  } catch {
    return null
  }
}

export default async function SharePage({ params }: { params: { token: string } }) {
  const share = await loadShare(params.token)

  if (!share) {
    return (
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold">Share link unavailable</h1>
        <p className="text-slate-600 dark:text-slate-300">
          This link is invalid or has expired. Ask the host to generate a new share link.
        </p>
        <Link
          href="/room"
          className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
        >
          Go to Room Lobby
        </Link>
      </section>
    )
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
          Shared story
        </p>
        <h1 className="text-2xl font-semibold">Story Reveal</h1>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Shared by the host. This link expires on {new Date(share.expires_at).toLocaleString()}.
        </p>
      </header>

      <div
        className="rounded-2xl border border-slate-200 bg-white p-6 text-lg leading-relaxed shadow-sm dark:border-slate-800 dark:bg-slate-950"
        role="region"
        aria-label="Shared story"
      >
        {share.rendered_story}
      </div>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/room"
          className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
        >
          Start a room
        </Link>
        <Link
          href="/mode"
          className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
        >
          Play solo
        </Link>
      </div>
    </section>
  )
}
