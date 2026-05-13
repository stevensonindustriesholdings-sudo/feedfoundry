import Link from "next/link";

export default function HomePage() {
  return (
    <div className="space-y-16 md:space-y-20">
      <section className="relative space-y-8">
        <div className="pointer-events-none absolute -left-4 top-0 h-32 w-32 rounded-full bg-accent/10 blur-3xl md:-left-8" />
        <p className="relative text-xs font-semibold uppercase tracking-[0.2em] text-accent">
          Creator archive platform
        </p>
        <h1 className="relative max-w-4xl text-4xl font-semibold tracking-tight text-zinc-50 md:text-5xl lg:text-[3.25rem] lg:leading-[1.1]">
          Preserved and enriched episodes, in your annual hosted archive.
        </h1>
        <p className="relative max-w-2xl text-lg leading-relaxed text-zinc-400">
          FeedFoundry turns video and audio into structured outputs—transcripts, chapters, show notes, metadata, CTAs,
          fact sheets, FAQs, and hosted manifests. You keep a <strong className="font-medium text-zinc-200">creator archive</strong>{" "}
          with <strong className="font-medium text-zinc-200">annual hosted archive</strong> access and{" "}
          <strong className="font-medium text-zinc-200">processing credits</strong> per job.
        </p>
        <div className="relative flex flex-wrap gap-3">
          <Link
            href="/pricing"
            className="inline-flex items-center justify-center rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-surface no-underline shadow-lg shadow-accent/10 hover:bg-accent/90"
          >
            View pricing
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-xl border border-surface-border bg-surface-raised/60 px-6 py-3 text-sm font-medium text-zinc-100 no-underline hover:border-zinc-600 hover:bg-surface-raised"
          >
            Dashboard
          </Link>
          <Link
            href="/upload"
            className="inline-flex items-center justify-center rounded-xl border border-transparent px-6 py-3 text-sm font-medium text-zinc-300 no-underline hover:text-zinc-100"
          >
            Upload media →
          </Link>
        </div>
      </section>

      <section className="grid gap-5 md:grid-cols-3">
        {[
          {
            title: "Annual hosted archive",
            body: "A stable home for processed outputs and public manifests—priced as archive access, not as a generic app seat.",
          },
          {
            title: "Processing credits",
            body: "Each job reserves credits up front. Larger files and richer output bundles may use more credits; you buy packs when you need capacity.",
          },
          {
            title: "Creator archive",
            body: "One place for preserved and enriched episodes—ready for your site, RSS, or downstream workflows.",
          },
        ].map((card) => (
          <article
            key={card.title}
            className="rounded-2xl border border-surface-border bg-surface-raised/50 p-6 shadow-sm shadow-black/20"
          >
            <h2 className="text-base font-semibold text-zinc-100">{card.title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-zinc-500">{card.body}</p>
          </article>
        ))}
      </section>

      <section className="rounded-2xl border border-surface-border bg-gradient-to-br from-surface-raised/80 to-surface-raised/30 p-8 md:p-10">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">How it works</h2>
        <ol className="mt-6 grid gap-8 md:grid-cols-3 md:gap-6">
          {[
            { step: "01", title: "Upload", desc: "Send media securely; choose which outputs you want generated." },
            { step: "02", title: "Track", desc: "Follow jobs and credit use from the dashboard through completion." },
            { step: "03", title: "Publish", desc: "Download deliverables and expose your public creator archive manifest." },
          ].map((s) => (
            <li key={s.step} className="relative pl-14 md:pl-0 md:pt-12">
              <span className="absolute left-0 top-0 font-mono text-xs text-accent md:left-0 md:top-0">{s.step}</span>
              <h3 className="font-medium text-zinc-100">{s.title}</h3>
              <p className="mt-2 text-sm text-zinc-500">{s.desc}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-2xl border border-surface-border/80 bg-surface-raised/25 px-6 py-8 md:px-10">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">Trust &amp; operations</h2>
        <ul className="mt-4 flex flex-wrap gap-x-10 gap-y-3 text-sm text-zinc-400">
          <li className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Stripe for purchases
          </li>
          <li className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            S3-compatible object storage
          </li>
          <li className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            OpenAPI processing pipeline
          </li>
        </ul>
      </section>
    </div>
  );
}
