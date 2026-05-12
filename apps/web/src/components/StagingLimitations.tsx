export function StagingLimitations() {
  const env = process.env.NEXT_PUBLIC_APP_ENV;
  if (env !== "staging") return null;
  return (
    <aside
      className="rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-amber-100"
      aria-label="Staging limitations"
    >
      <p className="font-medium text-amber-50">Staging honesty</p>
      <ul className="mt-2 list-inside list-disc space-y-1 text-amber-100/90">
        <li>Full AI transcription may still be stubbed; outputs can be vertical-slice artefacts.</li>
        <li>Stripe Checkout session creation may not be wired from this app yet — use Pricing placeholders.</li>
        <li>Annual access and credits require a configured org in the API (seed or live purchase).</li>
      </ul>
    </aside>
  );
}
