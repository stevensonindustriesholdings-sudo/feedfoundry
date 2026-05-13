import Link from "next/link";
import { StagingLimitations } from "@/components/StagingLimitations";

const pillars = [
  {
    title: "Structured outputs",
    body: "Transcripts, clean transcripts, chapters, clip candidates, show notes, metadata, CTAs, fact sheets, FAQs, and export-ready bundles.",
  },
  {
    title: "Hosted archive",
    body: "Annual hosted archive access keeps published manifests and exports addressable for your audience and tools.",
  },
  {
    title: "Fair processing",
    body: "Jobs draw from your included processing time; larger files and richer bundles use more time. No surprise “unlimited” claims.",
  },
] as const;

export default function HomePage() {
  return (
    <div className="space-y-16">
      <section className="relative overflow-hidden rounded-2xl border border-surface-border bg-gradient-to-br from-surface-raised via-surface to-surface-raised p-8 md:p-12">
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-accent/10 blur-3xl" aria-hidden />
        <div className="relative max-w-3xl space-y-6">
          <p className="text-sm font-medium uppercase tracking-wide text-accent">FeedFoundry</p>
          <h1 className="text-4xl font-semibold tracking-tight text-zinc-50 md:text-5xl lg:text-[3.25rem] lg:leading-tight">
            Creator media, preserved and enriched for the long term.
          </h1>
          <p className="max-w-2xl text-lg leading-relaxed text-zinc-400">
            Upload video or audio from your own library. FeedFoundry turns episodes into machine-readable archives you
            can search, cite, and republish — with <strong className="font-medium text-zinc-200">annual archive access</strong>{" "}
            and <strong className="font-medium text-zinc-200">processing time</strong> you control per job.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              href="/upload"
              className="inline-flex items-center justify-center rounded-lg bg-accent px-5 py-2.5 font-medium text-surface no-underline hover:bg-accent/90"
            >
              Upload media
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center rounded-lg border border-surface-border bg-surface/50 px-5 py-2.5 font-medium text-zinc-100 no-underline hover:bg-surface-raised"
            >
              Dashboard
            </Link>
            <Link
              href="/pricing"
              className="inline-flex items-center justify-center rounded-lg border border-transparent px-5 py-2.5 font-medium text-zinc-300 no-underline hover:text-zinc-100"
            >
              Plans &amp; processing packs →
            </Link>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">What you get</h2>
        <ul className="mt-6 grid gap-5 md:grid-cols-3">
          {pillars.map((p) => (
            <li
              key={p.title}
              className="rounded-xl border border-surface-border bg-surface-raised/30 p-5 transition-colors hover:border-accent/30"
            >
              <h3 className="font-semibold text-zinc-100">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-400">{p.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/25 px-6 py-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Built for operators</h2>
        <ul className="mt-3 flex flex-wrap gap-x-8 gap-y-2 text-sm text-zinc-400">
          <li>Stripe checkout (where wired)</li>
          <li>S3-compatible object storage</li>
          <li>OpenAPI-backed pipeline</li>
        </ul>
      </section>

      <StagingLimitations />
    </div>
  );
}
