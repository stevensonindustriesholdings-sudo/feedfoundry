import Link from "next/link";

export default function PricingPage() {
  return (
    <div className="space-y-12 md:space-y-16">
      <header className="max-w-2xl space-y-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Pricing</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">Archive access and processing time</h1>
        <p className="text-base leading-relaxed text-zinc-400">
          Your <strong className="font-medium text-zinc-300">annual hosted archive</strong> covers where outputs live.
          <strong className="font-medium text-zinc-300"> Processing time</strong> (minutes per job) powers each run—top
          up when you need more capacity. Checkout from this app will connect here when billing is enabled.
        </p>
      </header>

      <section className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 className="text-xl font-semibold text-zinc-100">Annual hosted archive</h2>
          <Link href="/dashboard" className="text-sm font-medium text-accent no-underline hover:underline">
            Check access in dashboard →
          </Link>
        </div>
        <p className="max-w-2xl text-sm text-zinc-500">
          Includes hosting for your processed outputs and public manifests for the term you purchase. Larger libraries
          and retention options are reflected at checkout.
        </p>
        <div className="grid gap-5 lg:grid-cols-2">
          <article className="relative overflow-hidden rounded-2xl border border-accent/25 bg-gradient-to-b from-accent/10 to-surface-raised/40 p-8 ring-1 ring-accent/20">
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">Primary</p>
            <h3 className="mt-2 text-2xl font-semibold text-zinc-50">Annual archive access</h3>
            <p className="mt-3 text-sm leading-relaxed text-zinc-400">
              Hosted archive for your creator archive: transcripts, chapters, metadata, CTAs, fact sheets, FAQs, and
              manifests—kept available for the year on your plan.
            </p>
            <p className="mt-8 font-mono text-3xl font-semibold tracking-tight text-zinc-100">Custom</p>
            <p className="mt-1 text-xs text-zinc-500">Final price at Stripe Checkout</p>
            <p className="mt-6 text-xs text-zinc-600">Stripe Checkout integration from this app is planned; until then, use your configured org in the API.</p>
          </article>
          <article className="rounded-2xl border border-surface-border bg-surface-raised/40 p-8">
            <h3 className="text-lg font-semibold text-zinc-100">What archive access includes</h3>
            <ul className="mt-4 space-y-3 text-sm text-zinc-400">
              <li className="flex gap-2">
                <span className="text-accent">✓</span>
                Storage-backed deliverables for completed jobs
              </li>
              <li className="flex gap-2">
                <span className="text-accent">✓</span>
                Public manifest URLs for your creator archive
              </li>
              <li className="flex gap-2">
                <span className="text-accent">✓</span>
                Clear hosting-until dates in your dashboard
              </li>
            </ul>
          </article>
        </div>
      </section>

      <section className="space-y-6">
        <h2 className="text-xl font-semibold text-zinc-100">Processing time top-ups</h2>
        <p className="max-w-2xl text-sm text-zinc-500">
          Processing minutes are reserved when a job is created and reconciled when work completes. Add top-ups
          alongside your archive plan when you batch-ingest seasons or back-catalog work.
        </p>
        <div className="grid gap-5 md:grid-cols-3">
          {[
            { name: "Starter", hint: "Light batches, pilots, and single shows.", minutes: "— minutes" },
            { name: "Growth", hint: "Season drops and steady publishing.", minutes: "— minutes", featured: true },
            { name: "Studio", hint: "Libraries, networks, and high volume.", minutes: "— minutes" },
          ].map((pack) => (
            <article
              key={pack.name}
              className={
                pack.featured
                  ? "rounded-2xl border border-accent/30 bg-surface-raised/60 p-6 ring-1 ring-accent/15"
                  : "rounded-2xl border border-surface-border bg-surface-raised/40 p-6"
              }
            >
              {pack.featured ? (
                <p className="text-xs font-semibold uppercase tracking-wider text-accent">Popular</p>
              ) : null}
              <h3 className={`font-semibold text-zinc-100 ${pack.featured ? "mt-2" : ""}`}>{pack.name}</h3>
              <p className="mt-2 text-sm text-zinc-500">{pack.hint}</p>
              <p className="mt-6 font-mono text-xl text-zinc-200">{pack.minutes}</p>
              <p className="mt-1 text-xs text-zinc-600">Checkout wiring from this app is planned.</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
