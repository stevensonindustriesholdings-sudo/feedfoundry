import Link from "next/link";
import { StagingLimitations } from "@/components/StagingLimitations";

export default function HomePage() {
  return (
    <div className="space-y-10">
      <section className="space-y-6">
        <p className="text-sm font-medium uppercase tracking-wide text-accent">Creator archive platform</p>
        <h1 className="text-4xl font-semibold tracking-tight text-zinc-50 md:text-5xl">
          Turn creator media into a hosted, structured archive.
        </h1>
        <p className="max-w-2xl text-lg text-zinc-300">
          FeedFoundry processes videos, podcasts, and creator episodes into transcripts, chapters, show notes,
          metadata, CTAs, fact sheets, FAQs, and hosted manifests — with{" "}
          <strong className="text-zinc-200">annual archive access</strong> and{" "}
          <strong className="text-zinc-200">processing credits</strong> consumed per job.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/pricing"
            className="inline-flex items-center justify-center rounded-lg bg-accent px-5 py-2.5 font-medium text-surface no-underline hover:bg-accent/90"
          >
            View pricing
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-lg border border-surface-border px-5 py-2.5 font-medium text-zinc-100 no-underline hover:bg-surface-raised"
          >
            Open dashboard
          </Link>
          <Link
            href="/upload"
            className="inline-flex items-center justify-center rounded-lg border border-surface-border px-5 py-2.5 font-medium text-zinc-100 no-underline hover:bg-surface-raised"
          >
            Upload media
          </Link>
        </div>
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Trust</h2>
        <ul className="mt-3 flex flex-wrap gap-6 text-sm text-zinc-300">
          <li>Stripe billing</li>
          <li>S3-compatible object storage (R2-ready)</li>
          <li>OpenAPI-backed processing pipeline</li>
        </ul>
      </section>

      <StagingLimitations />
    </div>
  );
}
