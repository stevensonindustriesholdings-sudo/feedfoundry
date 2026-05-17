import { forwardToFeedFoundry } from "@/lib/server/feedfoundry-upstream";
import { OrgSwitcher } from "@/components/OrgSwitcher";

export const dynamic = "force-dynamic";

export default async function SystemPage() {
  let healthJson: unknown = null;
  let readyJson: unknown = null;
  let hintsJson: unknown = null;
  let healthErr: string | null = null;
  let readyErr: string | null = null;
  let hintsErr: string | null = null;

  try {
    const h = await forwardToFeedFoundry("/health");
    const t = await h.text();
    if (!h.ok) healthErr = `HTTP ${h.status}: ${t.slice(0, 200)}`;
    else healthJson = JSON.parse(t);
  } catch (e) {
    healthErr = (e as Error).message;
  }
  try {
    const r = await forwardToFeedFoundry("/ready");
    const t = await r.text();
    if (!r.ok) readyErr = `HTTP ${r.status}: ${t.slice(0, 200)}`;
    else readyJson = JSON.parse(t);
  } catch (e) {
    readyErr = (e as Error).message;
  }
  try {
    const w = await forwardToFeedFoundry("/v1/system/worker-hints");
    const tw = await w.text();
    if (!w.ok) hintsErr = `HTTP ${w.status}: ${tw.slice(0, 200)}`;
    else hintsJson = JSON.parse(tw);
  } catch (e) {
    hintsErr = (e as Error).message;
  }

  const base = process.env.NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL || "";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-50">System</h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          Staging visibility — not primary customer UX. Probes run server-side with your configured API base URL.
        </p>
      </div>

      <OrgSwitcher />

      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <article className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
          <h2 className="text-sm font-semibold text-zinc-300">GET /health</h2>
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-black/40 p-2 text-xs text-zinc-300">
            {healthErr ?? JSON.stringify(healthJson, null, 2)}
          </pre>
        </article>
        <article className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
          <h2 className="text-sm font-semibold text-zinc-300">GET /ready</h2>
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-black/40 p-2 text-xs text-zinc-300">
            {readyErr ?? JSON.stringify(readyJson, null, 2)}
          </pre>
        </article>
        <article className="rounded-xl border border-surface-border bg-surface-raised/40 p-4 md:col-span-2 lg:col-span-1">
          <h2 className="text-sm font-semibold text-zinc-300">GET /v1/system/worker-hints</h2>
          <p className="mt-1 text-xs text-zinc-500">Provider flags only — keys stay server-side.</p>
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-black/40 p-2 text-xs text-zinc-300">
            {hintsErr ?? JSON.stringify(hintsJson, null, 2)}
          </pre>
        </article>
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-4 text-sm">
        <h2 className="font-semibold text-zinc-300">OpenAPI</h2>
        <ul className="mt-2 space-y-2 text-zinc-400">
          <li>
            <a href={`${base}/docs`} className="text-accent" target="_blank" rel="noreferrer">
              Interactive docs →
            </a>
          </li>
          <li>
            <a href={`${base}/openapi.json`} className="text-accent" target="_blank" rel="noreferrer">
              openapi.json →
            </a>
          </li>
        </ul>
      </section>

      <p className="text-xs text-zinc-600">
        Internal API key is never sent to the browser — only this server process reads{" "}
        <code className="rounded bg-black/30 px-1">FEEDFOUNDRY_INTERNAL_API_KEY</code>.
      </p>
    </div>
  );
}
