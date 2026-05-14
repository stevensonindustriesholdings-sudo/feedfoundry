import { forwardToFeedFoundry } from "@/lib/server/feedfoundry-upstream";
import { getServerConfig } from "@/lib/server/config";
import { OrgSwitcher } from "@/components/OrgSwitcher";

export const dynamic = "force-dynamic";

function parseFlatApiError(status: number, text: string): string {
  try {
    const j = JSON.parse(text) as { code?: string; message?: string };
    if (j && typeof j.code === "string") {
      return `${j.code}: ${j.message ?? ""}`.trim();
    }
  } catch {
    /* ignore */
  }
  return `HTTP ${status}: ${text.slice(0, 200)}`;
}

type SystemSearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function SystemPage(props: { searchParams?: SystemSearchParams }) {
  let healthJson: unknown = null;
  let readyJson: unknown = null;
  let healthErr: string | null = null;
  let readyErr: string | null = null;
  let aiRunsJson: unknown = null;
  let aiRunsErr: string | null = null;

  const sp = (await props.searchParams) ?? {};
  const jobFilterRaw = sp.job;
  const jobFilter = typeof jobFilterRaw === "string" && jobFilterRaw.trim() ? jobFilterRaw.trim() : undefined;

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
    const { defaultOrgId } = getServerConfig();
    const params = new URLSearchParams({
      organisation_id: defaultOrgId,
      limit: "20",
    });
    if (jobFilter) params.set("job_id", jobFilter);
    const ar = await forwardToFeedFoundry(`/v1/admin/ai-runs?${params.toString()}`);
    const at = await ar.text();
    if (!ar.ok) aiRunsErr = parseFlatApiError(ar.status, at);
    else aiRunsJson = JSON.parse(at);
  } catch (e) {
    aiRunsErr = (e as Error).message;
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

      <section className="grid gap-4 md:grid-cols-2">
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
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-4 text-sm">
        <h2 className="font-semibold text-zinc-300">AI run status (internal)</h2>
        <p className="mt-2 max-w-3xl text-xs text-zinc-500">
          Read-only operational readout from <code className="rounded bg-black/30 px-1">GET /v1/admin/ai-runs</code> for
          the default org. Stages show validation status and mock provider names when persisted — not customer billing
          fields. OpenAI canary stays disabled unless you explicitly enable it on the worker host (
          <code className="rounded bg-black/30 px-1">AI_STRUCTURED_PROVIDER_MODE</code>); local dev normally uses the
          mock provider.
        </p>
        <p className="mt-2 text-xs text-zinc-500">
          Optional filter: append <code className="rounded bg-black/30 px-1">?job=&lt;job_id&gt;</code> to this page URL
          to scope the list.
        </p>
        <pre className="mt-3 max-h-80 overflow-auto rounded bg-black/40 p-2 text-xs text-zinc-300">
          {aiRunsErr ?? JSON.stringify(aiRunsJson, null, 2)}
        </pre>
        {aiRunsErr?.includes("404") || aiRunsErr?.includes("not_found") ? (
          <p className="mt-2 text-xs text-zinc-600">
            If the route is missing, deploy an API that includes admin AI run routes, then reload.
          </p>
        ) : null}
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
