import Link from "next/link"

export default function LandingPage() {
  return (
    <section className="space-y-10">
      <header className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          StoryFill
        </p>
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
          Choose how you want to play.
        </h1>
        <p className="max-w-2xl text-base text-muted-foreground">
          Start solo to jump straight into prompts, or spin up a multiplayer room to host friends.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Link
          href="/templates?mode=solo"
          className="focus-ring flex h-full flex-col gap-4 rounded-2xl border bg-card p-6 text-left shadow-sm transition hover:border-ring"
        >
          <div className="space-y-2">
            <p className="text-lg font-semibold">Solo</p>
            <p className="text-sm text-muted-foreground">
              Pick a template and dive right into prompts.
            </p>
          </div>
          <span className="text-sm text-muted-foreground">
            Best for a quick story on your own.
          </span>
        </Link>

        <Link
          href="/room"
          className="focus-ring flex h-full flex-col gap-4 rounded-2xl border bg-card p-6 text-left shadow-sm transition hover:border-ring"
        >
          <div className="space-y-2">
            <p className="text-lg font-semibold">Multiplayer</p>
            <p className="text-sm text-muted-foreground">
              Create a room, invite players, and pick a shared template.
            </p>
          </div>
          <span className="text-sm text-muted-foreground">
            Host-led flow with live lobby updates.
          </span>
        </Link>
      </div>

      <div className="rounded-2xl border bg-card p-6 text-sm text-muted-foreground shadow-sm">
        <h2 className="text-base font-semibold text-foreground">Multiplayer flow</h2>
        <ol className="mt-3 grid gap-2">
          <li>1. Create or join a room.</li>
          <li>2. Choose the story template together.</li>
          <li>3. Start the game when everyone is ready.</li>
        </ol>
      </div>
    </section>
  )
}
