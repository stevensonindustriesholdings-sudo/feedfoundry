import { StagingLimitations } from "@/components/StagingLimitations";

export default function PricingPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-50">Pricing</h1>
        <p className="mt-2 max-w-2xl text-zinc-400">
          Credits are consumed by processing jobs. Larger files and richer output bundles may use more credits.
          Credit expiry and rollover follow the active product policy.
        </p>
      </div>

      <section>
        <h2 className="text-xl font-medium text-zinc-100">Annual archive access</h2>
        <p className="mt-2 text-sm text-zinc-400">
          Hosted archive access for your processed outputs — not a monthly subscription for unlimited processing.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <article className="rounded-xl border border-surface-border bg-surface-raised/50 p-5">
            <h3 className="font-semibold text-zinc-100">Annual Archive Access</h3>
            <p className="mt-2 text-sm text-zinc-400">Placeholder — Stripe Checkout for annual plans will wire here.</p>
          </article>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-medium text-zinc-100">Processing credit packs</h2>
        <p className="mt-2 text-sm text-zinc-400">Add-on credits for processing jobs alongside included credits.</p>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {["Starter Credit Pack", "Growth Credit Pack", "Studio Credit Pack"].map((name) => (
            <article key={name} className="rounded-xl border border-surface-border bg-surface-raised/50 p-5">
              <h3 className="font-semibold text-zinc-100">{name}</h3>
              <p className="mt-2 text-sm text-zinc-400">Placeholder — checkout wiring pending.</p>
            </article>
          ))}
        </div>
      </section>

      <StagingLimitations />
    </div>
  );
}
