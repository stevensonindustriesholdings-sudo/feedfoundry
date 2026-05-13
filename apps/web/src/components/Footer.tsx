import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-surface-border/80 bg-surface-raised/30">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-10 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
        <p className="m-0">© {new Date().getFullYear()} FeedFoundry · Creator archive</p>
        <nav className="flex flex-wrap gap-x-6 gap-y-2" aria-label="Footer">
          <Link href="/pricing" className="text-zinc-400 no-underline hover:text-zinc-200">
            Pricing
          </Link>
          <Link href="/archive" className="text-zinc-400 no-underline hover:text-zinc-200">
            Public archive
          </Link>
          <Link href="/system" className="text-zinc-600 no-underline hover:text-zinc-400">
            Service &amp; API
          </Link>
        </nav>
      </div>
    </footer>
  );
}
