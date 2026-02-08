import Link from "next/link"

export default function ExpiredPage() {
  return (
    <section className="space-y-5">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Room expired</h1>
        <p className="text-slate-600 dark:text-slate-300">
          This room was inactive for over an hour. Start a new room to keep playing.
        </p>
      </header>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/room"
          className="btn-primary"
        >
          Create or Join a Room
        </Link>
        <Link
          href="/templates?mode=solo"
          className="btn-secondary"
        >
          Play Solo
        </Link>
      </div>
    </section>
  )
}
