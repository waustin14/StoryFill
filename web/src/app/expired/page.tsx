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
          className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
        >
          Create or Join a Room
        </Link>
        <Link
          href="/mode"
          className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-500 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
        >
          Play Solo
        </Link>
      </div>
    </section>
  )
}
