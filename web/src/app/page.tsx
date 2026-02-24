import Link from "next/link"

const steps = [
  "Create or join a room with a short code",
  "Host picks the story template",
  "Everyone fills in their prompts — blind",
  "Host reveals the completed story to the room",
]

export default function LandingPage() {
  return (
    <section className="space-y-12 py-4">
      <header className="space-y-5">
        <p className="font-mono text-xs font-bold uppercase tracking-[0.35em] text-primary">
          StoryFill
        </p>
        <h1 className="font-display text-5xl font-black leading-[1.05] tracking-tight text-foreground md:text-6xl">
          Pick your words.<br />
          <em className="text-primary not-italic">Make a story.</em>
        </h1>
        <p className="max-w-md text-base leading-relaxed text-muted-foreground">
          Fill in the blanks, then watch the chaos unfold. Play solo or host a room with friends.
        </p>
      </header>

      <div className="grid gap-5 md:grid-cols-2">
        <Link
          href="/templates?mode=solo"
          className="focus-ring group flex flex-col justify-between gap-8 rounded-2xl border bg-card p-7 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md"
        >
          <span
            aria-hidden
            className="font-display text-7xl font-black leading-none text-border transition-colors duration-200 group-hover:text-primary/15 select-none"
          >
            01
          </span>
          <div className="space-y-2">
            <p className="text-xl font-bold">Solo</p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Pick a template and dive straight into prompts. Your story, instantly.
            </p>
          </div>
        </Link>

        <Link
          href="/room"
          className="focus-ring group flex flex-col justify-between gap-8 rounded-2xl border bg-card p-7 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md"
        >
          <span
            aria-hidden
            className="font-display text-7xl font-black leading-none text-border transition-colors duration-200 group-hover:text-primary/15 select-none"
          >
            02
          </span>
          <div className="space-y-2">
            <p className="text-xl font-bold">Multiplayer</p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Create a room, invite players, pick a template, and reveal the story together.
            </p>
          </div>
        </Link>
      </div>

      <div className="rounded-2xl border bg-card p-6 shadow-sm">
        <p className="mb-5 font-mono text-xs font-bold uppercase tracking-[0.3em] text-muted-foreground">
          Multiplayer flow
        </p>
        <ol className="space-y-4">
          {steps.map((step, i) => (
            <li key={i} className="flex items-center gap-4">
              <span className="font-mono text-sm font-bold tabular-nums text-primary/60">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="text-sm text-foreground">{step}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
