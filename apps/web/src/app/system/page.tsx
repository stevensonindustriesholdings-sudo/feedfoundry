import Link from "next/link";
import { OrgSwitcher } from "@/components/OrgSwitcher";
import { ConnectivityTools } from "@/components/ConnectivityTools";
import { probePublicHealth, probePublicReady, probeProxyAccountCredits } from "@/lib/server/system-probes";

export const dynamic = "force-dynamic";

function redactSnippet(s: string): string {
  return s.replace(/Bearer\s+[\w-._~+/=]+/gi, "Bearer [redacted]");
}

function ProbeRow({ label, probe }: { label: string; probe: { url: string; httpStatus: number; ok: boolean; snippet: string; error?: string } }) {
  const tone = probe.error ? "text-red-300" : probe.ok ? "text-emerald-400/90" : "text-amber-200";
  return (
    <tr className="border-b border-surface-border/60 align-top">
      <td className="py-3 pr-4 text-xs font-medium text-zinc-500">{label}</td>
      <td className="py-3 pr-4 font-mono text-[11px] text-zinc-500 break-all">{probe.url}</td>
      <td className={`py-3 pr-4 font-mono text-xs ${tone}`}>{probe.error ? "ERR" : probe.httpStatus}</td>
      <td className="py-3 text-xs text-zinc-400">
        {probe.error ? <span className="text-red-300">{probe.error}</span> : <span className={tone}>{probe.ok ? "OK" : "HTTP error"}</span>}
        {probe.snippet ? (
          <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-black/35 p-2 font-mono text-[10px] text-zinc-500">
            {redactSnippet(probe.snippet)}
          </pre>
        ) : null}
      </td>
    </tr>
  );
}

export default async function SystemPage() {
  const publicBase = process.env.NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL?.replace(/\/$/, "") || "";
  const pubHealth = publicBase ? await probePublicHealth(publicBase) : null;
  const pubReady = publicBase ? await probePublicReady(publicBase) : null;
  const proxyCredits = await probeProxyAccountCredits();

  const docsBase = publicBase;

  return (
    <div className="space-y-10">
      <div className="max-w-2xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Operators</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">Service &amp; API</h1>
        <p className="text-sm leading-relaxed text-zinc-500">
          Public probes hit the Railway URL from this server (no internal key). The credits row calls your{" "}
          <strong className="text-zinc-400">local Next proxy</strong> so it matches the Dashboard path (internal key
          stays server-side).
        </p>
      </div>

      <OrgSwitcher />

      <section className="rounded-2xl border border-surface-border bg-surface-raised/35 p-5 md:p-6">
        <h2 className="text-sm font-semibold text-zinc-200">API reachability</h2>
        <p className="mt-1 text-xs text-zinc-500">
          NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL: {publicBase || "(not set)"}
        </p>
        {!publicBase ? (
          <p className="mt-3 text-sm text-amber-200">Set NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL for public health/ready checks.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[32rem] border-collapse text-left">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-zinc-600">
                  <th className="pb-2 pr-4 font-medium">Check</th>
                  <th className="pb-2 pr-4 font-medium">URL</th>
                  <th className="pb-2 pr-4 font-medium">HTTP</th>
                  <th className="pb-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                {pubHealth ? <ProbeRow label="Public GET /health" probe={pubHealth} /> : null}
                {pubReady ? <ProbeRow label="Public GET /ready" probe={pubReady} /> : null}
                <ProbeRow label="Proxy GET /v1/account/credits (via /api/ff)" probe={proxyCredits} />
              </tbody>
            </table>
          </div>
        )}
      </section>

      <ConnectivityTools />

      <section className="rounded-2xl border border-surface-border bg-surface-raised/35 p-5 md:p-6">
        <h2 className="text-sm font-semibold text-zinc-200">R2 storage viewer</h2>
        <p className="mt-1 text-xs text-zinc-500">
          List objects in the staging bucket using server-side credentials (nothing secret in the browser).
        </p>
        <p className="mt-3">
          <Link
            href="/system/storage"
            className="text-sm font-semibold text-accent no-underline hover:underline"
          >
            Open storage viewer →
          </Link>
        </p>
      </section>

      <section className="rounded-2xl border border-surface-border bg-surface-raised/35 p-6 text-sm">
        <h2 className="font-semibold text-zinc-200">OpenAPI</h2>
        <ul className="mt-3 space-y-2 text-zinc-500">
          <li>
            <a href={`${docsBase}/docs`} className="font-medium text-accent" target="_blank" rel="noreferrer">
              Interactive docs
            </a>
          </li>
          <li>
            <a href={`${docsBase}/openapi.json`} className="font-medium text-accent" target="_blank" rel="noreferrer">
              openapi.json
            </a>
          </li>
        </ul>
      </section>

      <p className="text-xs leading-relaxed text-zinc-600">
        <code className="rounded bg-black/30 px-1 py-0.5">FEEDFOUNDRY_INTERNAL_API_KEY</code> is read only in Next
        server code (proxy route handlers and <code className="rounded bg-black/30 px-1">src/lib/server/*</code>) —
        never <code className="rounded bg-black/30 px-1">NEXT_PUBLIC_*</code> and never sent to the browser.{" "}
        <Link href="/dashboard" className="text-zinc-500 underline-offset-2 hover:text-zinc-400">
          Dashboard
        </Link>{" "}
        uses the same-origin proxy only.
      </p>
    </div>
  );
}
