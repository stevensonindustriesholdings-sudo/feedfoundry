"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { browserGet, browserPost } from "@/lib/client/api";
import { getOrgId } from "@/lib/org-storage";
import type {
  AdminProviderConfigsResponse,
  AdminYoutubeQueueResponse,
  JobListResponse,
  WorkerHintsResponse,
  YoutubeQueueEnqueueResponse,
  YoutubeQueueListResponse,
} from "@/lib/types";
import { OUTPUT_OPTIONS } from "@/lib/types";
import type { ClientError } from "@/lib/errors";

function firstAuthError(...errors: (ClientError | null)[]): ClientError | null {
  for (const e of errors) {
    if (e?.code === "unauthorized") return e;
  }
  return null;
}

export default function PortalPage() {
  const orgId = useMemo(() => getOrgId(), []);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [youtubeBusy, setYoutubeBusy] = useState(false);
  const [youtubeOk, setYoutubeOk] = useState<YoutubeQueueEnqueueResponse | null>(null);
  const [youtubeErr, setYoutubeErr] = useState<ClientError | null>(null);

  const [orgQueue, setOrgQueue] = useState<YoutubeQueueListResponse | null>(null);
  const [orgQueueErr, setOrgQueueErr] = useState<ClientError | null>(null);

  const [adminQueue, setAdminQueue] = useState<AdminYoutubeQueueResponse | null>(null);
  const [adminQueueErr, setAdminQueueErr] = useState<ClientError | null>(null);

  const [providers, setProviders] = useState<AdminProviderConfigsResponse | null>(null);
  const [providersErr, setProvidersErr] = useState<ClientError | null>(null);

  const [recentJobs, setRecentJobs] = useState<JobListResponse | null>(null);
  const [recentJobsErr, setRecentJobsErr] = useState<ClientError | null>(null);

  const [hints, setHints] = useState<WorkerHintsResponse | null>(null);
  const [hintsErr, setHintsErr] = useState<ClientError | null>(null);

  const [refreshKey, setRefreshKey] = useState(0);

  const refreshQueues = useCallback(async () => {
    setOrgQueueErr(null);
    setAdminQueueErr(null);
    setProvidersErr(null);
    setRecentJobsErr(null);
    setHintsErr(null);

    const [oq, aq, pv, jh, wh] = await Promise.all([
      browserGet<YoutubeQueueListResponse>("/v1/youtube-source-queue?limit=50&offset=0", orgId),
      browserGet<AdminYoutubeQueueResponse>("/v1/admin/youtube-queue?limit=100", orgId),
      browserGet<AdminProviderConfigsResponse>("/v1/admin/provider-configs", orgId),
      browserGet<JobListResponse>("/v1/jobs?limit=15&offset=0", orgId),
      browserGet<WorkerHintsResponse>("/v1/system/worker-hints", orgId),
    ]);

    if (oq.ok) setOrgQueue(oq.data);
    else {
      setOrgQueue(null);
      setOrgQueueErr(oq.error);
    }
    if (aq.ok) setAdminQueue(aq.data);
    else {
      setAdminQueue(null);
      setAdminQueueErr(aq.error);
    }
    if (pv.ok) setProviders(pv.data);
    else {
      setProviders(null);
      setProvidersErr(pv.error);
    }
    if (jh.ok) setRecentJobs(jh.data);
    else {
      setRecentJobs(null);
      setRecentJobsErr(jh.error);
    }
    if (wh.ok) setHints(wh.data);
    else {
      setHints(null);
      setHintsErr(wh.error);
    }
  }, [orgId]);

  useEffect(() => {
    void refreshQueues();
  }, [refreshQueues, refreshKey]);

  const authBanner = firstAuthError(
    orgQueueErr,
    adminQueueErr,
    providersErr,
    recentJobsErr,
    hintsErr,
    youtubeErr,
  );

  const submitYoutube = async () => {
    setYoutubeBusy(true);
    setYoutubeErr(null);
    setYoutubeOk(null);
    const u = youtubeUrl.trim();
    if (!u) {
      setYoutubeBusy(false);
      setYoutubeErr({
        code: "bad_request",
        status: 400,
        message: "Paste a public YouTube watch, Shorts, or youtu.be link.",
      });
      return;
    }
    const r = await browserPost<YoutubeQueueEnqueueResponse>("/v1/youtube-source-queue", { youtube_url: u }, orgId);
    setYoutubeBusy(false);
    if (!r.ok) {
      setYoutubeErr(r.error);
      return;
    }
    setYoutubeOk(r.data);
    setYoutubeUrl("");
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-zinc-50">Customer / admin portal</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-400">
            YouTube URL backlog for your org, operator-wide admin queue, recent processing jobs, AI provider routing
            (no secrets), and worker capability hints. All calls go through the Next.js BFF — keys stay server-side.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setRefreshKey((k) => k + 1)}
          className="rounded-lg border border-surface-border bg-surface-raised px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-surface-border/40"
        >
          Refresh data
        </button>
      </div>

      {authBanner ? (
        <div role="alert" className="rounded-lg border border-danger/50 bg-danger/10 px-4 py-3 text-sm text-red-100">
          <p className="font-semibold">Authentication / proxy error</p>
          <p className="mt-1">{authBanner.message}</p>
          <p className="mt-2 text-red-100/80">
            Org header in use: <code className="rounded bg-black/30 px-1">{orgId || "(default from server)"}</code> —
            confirm <code className="rounded bg-black/30 px-1">FEEDFOUNDRY_INTERNAL_API_KEY</code> on the web host and{" "}
            <code className="rounded bg-black/30 px-1">FF_INTERNAL_API_KEY</code> on the API match.
          </p>
        </div>
      ) : null}

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
        <h2 className="text-lg font-semibold text-zinc-100">Submit YouTube link (org queue)</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Records intent only — no download or scraping. POST <span className="font-mono">/v1/youtube-source-queue</span>
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <input
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=…"
            className="min-w-[240px] flex-1 rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
          />
          <button
            type="button"
            disabled={youtubeBusy}
            onClick={() => void submitYoutube()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface hover:bg-accent/90 disabled:opacity-50"
          >
            {youtubeBusy ? "Submitting…" : "Enqueue"}
          </button>
        </div>
        {youtubeErr && youtubeErr.code !== "unauthorized" ? (
          <p className="mt-2 text-sm text-red-300">{youtubeErr.message}</p>
        ) : null}
        {youtubeOk ? (
          <p className="mt-2 text-sm text-accent">
            Queued <span className="font-mono text-zinc-300">{youtubeOk.id}</span> — {youtubeOk.detail ?? youtubeOk.status}
          </p>
        ) : null}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <QueueTable
          title="Your organisation — YouTube queue"
          subtitle="GET /v1/youtube-source-queue"
          error={orgQueueErr?.code === "unauthorized" ? null : orgQueueErr}
          empty={!orgQueue?.items.length}
        >
          {orgQueue?.items.length ? (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-xs uppercase text-zinc-500">
                  <th className="py-2 pr-2">Status</th>
                  <th className="py-2 pr-2">URL</th>
                  <th className="py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {orgQueue.items.map((row) => (
                  <tr key={row.id} className="border-b border-surface-border/60">
                    <td className="py-2 pr-2 font-mono text-xs text-zinc-300">{row.status}</td>
                    <td className="max-w-[200px] truncate py-2 pr-2 text-zinc-400">
                      <a href={row.youtube_url} className="text-accent hover:underline" target="_blank" rel="noreferrer">
                        {row.youtube_url}
                      </a>
                    </td>
                    <td className="whitespace-nowrap py-2 text-xs text-zinc-500">{row.created_at ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </QueueTable>

        <QueueTable
          title="Admin — all organisations"
          subtitle="GET /v1/admin/youtube-queue (internal key via BFF)"
          error={adminQueueErr?.code === "unauthorized" ? null : adminQueueErr}
          empty={!adminQueue?.items.length}
        >
          {adminQueue?.items.length ? (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-xs uppercase text-zinc-500">
                  <th className="py-2 pr-2">Org</th>
                  <th className="py-2 pr-2">Status</th>
                  <th className="py-2 pr-2">URL</th>
                  <th className="py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {adminQueue.items.map((row) => (
                  <tr key={row.id} className="border-b border-surface-border/60">
                    <td className="py-2 pr-2 font-mono text-xs text-zinc-400">{row.organisation_id}</td>
                    <td className="py-2 pr-2 font-mono text-xs text-zinc-300">{row.status}</td>
                    <td className="max-w-[160px] truncate py-2 pr-2 text-zinc-400">
                      <a href={row.youtube_url} className="text-accent hover:underline" target="_blank" rel="noreferrer">
                        {row.youtube_url}
                      </a>
                    </td>
                    <td className="whitespace-nowrap py-2 text-xs text-zinc-500">{row.created_at ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </QueueTable>
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
        <h2 className="text-lg font-semibold text-zinc-100">Worker &amp; provider panel</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Hints: <span className="font-mono">GET /v1/system/worker-hints</span> — Provider rows:{" "}
          <span className="font-mono">GET /v1/admin/provider-configs</span>
        </p>
        {hintsErr && hintsErr.code !== "unauthorized" ? (
          <p className="mt-2 text-sm text-red-300">{hintsErr.message}</p>
        ) : null}
        {hints ? (
          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <Hint label="AI live calls enabled" value={String(hints.ff_ai_live_calls_enabled)} />
            <Hint label="OpenAI configured" value={String(hints.openai_configured)} />
            <Hint label="OpenRouter configured" value={String(hints.openrouter_configured)} />
            <Hint label="AI modules loaded" value={String(hints.ai_routing_modules_loaded)} />
            <Hint label="YouTube queue API" value={String(hints.youtube_source_queue_enabled)} />
          </dl>
        ) : null}
        {hints?.notes ? <p className="mt-3 text-xs text-zinc-500">{hints.notes}</p> : null}

        {providersErr && providersErr.code !== "unauthorized" ? (
          <p className="mt-4 text-sm text-red-300">{providersErr.message}</p>
        ) : null}
        {providers?.provider_configs?.length ? (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-xs uppercase text-zinc-500">
                  <th className="py-2 pr-2">Provider</th>
                  <th className="py-2 pr-2">Model</th>
                  <th className="py-2 pr-2">Module</th>
                  <th className="py-2 pr-2">On</th>
                  <th className="py-2 pr-2">Priority</th>
                  <th className="py-2 pr-2">Fallback</th>
                </tr>
              </thead>
              <tbody>
                {providers.provider_configs.map((c) => (
                  <tr key={String(c.id)} className="border-b border-surface-border/60">
                    <td className="py-2 pr-2 font-mono text-xs">{String(c.provider)}</td>
                    <td className="py-2 pr-2 font-mono text-xs text-zinc-400">{String(c.model)}</td>
                    <td className="py-2 pr-2 text-zinc-400">{String(c.module_name)}</td>
                    <td className="py-2 pr-2">{c.enabled ? "yes" : "no"}</td>
                    <td className="py-2 pr-2">{String(c.priority ?? "—")}</td>
                    <td className="max-w-[180px] truncate py-2 pr-2 text-xs text-zinc-500">
                      {c.fallback_provider ? `${String(c.fallback_provider)} / ${String(c.fallback_model ?? "")}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-sm text-zinc-500">No provider config rows yet (empty table is normal on fresh env).</p>
        )}
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Recent jobs</h2>
            <p className="mt-1 text-xs text-zinc-500">GET /v1/jobs — same list as Processing page</p>
          </div>
          <Link href="/jobs" className="text-sm text-accent hover:underline">
            Open Processing →
          </Link>
        </div>
        {recentJobsErr && recentJobsErr.code !== "unauthorized" ? (
          <p className="mt-2 text-sm text-red-300">{recentJobsErr.message}</p>
        ) : null}
        {recentJobs?.jobs?.length ? (
          <table className="mt-4 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-xs uppercase text-zinc-500">
                <th className="py-2 pr-2">Job</th>
                <th className="py-2 pr-2">Status</th>
                <th className="py-2 pr-2">Stage</th>
                <th className="py-2">Progress</th>
              </tr>
            </thead>
            <tbody>
              {recentJobs.jobs.map((j) => (
                <tr key={j.job_id} className="border-b border-surface-border/60">
                  <td className="py-2 pr-2 font-mono text-xs text-zinc-300">{j.job_id}</td>
                  <td className="py-2 pr-2">{j.status}</td>
                  <td className="py-2 pr-2 text-zinc-500">{j.current_stage ?? "—"}</td>
                  <td className="py-2">{j.progress_percent ?? 0}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="mt-4 text-sm text-zinc-500">No jobs yet — upload media from Upload.</p>
        )}
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Outputs (placeholders)</h2>
            <p className="mt-1 text-xs text-zinc-500">
              After a job completes, artifacts appear under Outputs / Archive. Planned output types:
            </p>
          </div>
          <Link href="/outputs" className="text-sm text-accent hover:underline">
            Outputs →
          </Link>
        </div>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2 md:grid-cols-3">
          {OUTPUT_OPTIONS.map((o) => (
            <li key={o.id} className="rounded-lg border border-surface-border/80 bg-surface/40 px-3 py-2 text-sm text-zinc-300">
              {o.label}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function QueueTable({
  title,
  subtitle,
  error,
  empty,
  children,
}: {
  title: string;
  subtitle: string;
  error: ClientError | null;
  empty: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
      <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
      <p className="mt-1 text-xs text-zinc-500">{subtitle}</p>
      {error ? <p className="mt-2 text-sm text-red-300">{error.message}</p> : null}
      {empty && !error ? <p className="mt-4 text-sm text-zinc-500">No rows yet.</p> : null}
      {children}
    </div>
  );
}

function Hint({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-border/80 bg-surface/30 px-3 py-2">
      <dt className="text-xs uppercase text-zinc-500">{label}</dt>
      <dd className="mt-1 font-mono text-sm text-zinc-200">{value}</dd>
    </div>
  );
}
