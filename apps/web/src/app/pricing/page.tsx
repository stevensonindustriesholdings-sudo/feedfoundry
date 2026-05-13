import { StagingLimitations } from "@/components/StagingLimitations";

const processingPacks = ["Starter", "Growth", "Studio"] as const;

export default function PricingPage() {
  return (
    <div className="space-y-10">
      <header className="max-w-2xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Commercial</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50">Pricing</h1>
        <p className="text-sm leading-relaxed text-zinc-400">
          Annual hosted archive access plus metered processing time for jobs. Heavier files and richer output sets use
          more time. Renewal, rollover, and expiry follow the active product policy — wire Stripe Checkout from this
          surface when ready.
        </p>
      </header>

      <section>
        <h2 className="text-xl font-medium text-zinc-100">Annual archive access</h2>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          Hosted archive for processed outputs and manifests — priced annually, not as an unlimited monthly SaaS
          subscription.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <article className="rounded-xl border border-surface-border bg-surface-raised/50 p-5">
            <h3 className="font-semibold text-zinc-100">Annual archive access</h3>
            <p className="mt-2 text-sm text-zinc-400">
              Placeholder — Stripe Checkout for annual plans will wire here. Expected:{" "}
              <span className="font-mono text-zinc-500">POST /v1/…/checkout</span> (TODO).
            </p>
          </article>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-medium text-zinc-100">Processing time packs</h2>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          Add-on processing hours for busy seasons, alongside the time included with your annual access.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {processingPacks.map((name) => (
            <article key={name} className="rounded-xl border border-surface-border bg-surface-raised/50 p-5">
              <h3 className="font-semibold text-zinc-100">{name} processing pack</h3>
              <p className="mt-2 text-sm text-zinc-400">Placeholder — checkout wiring pending.</p>
            </article>
          ))}
        </div>
      </section>

      <StagingLimitations />
    </div>
  );
}
