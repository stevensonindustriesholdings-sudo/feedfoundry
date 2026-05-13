"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { browserGet } from "@/lib/client/api";
import { getLatestJobId, getOrgId, setLatestJobId } from "@/lib/org-storage";
import type { JobStatusResponse } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";

export default function JobsPage() {
  const [jobId, setJobId] = useState("");
  const [data, setData] = useState<JobStatusResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    const j = getLatestJobId();
    if (j) setJobId(j);
  }, []);

  const fetchJob = useCallback(async () => {
    if (!jobId.trim()) return;
    setErr(null);
    const r = await browserGet<JobStatusResponse>(`/v1/jobs/${encodeURIComponent(jobId.trim())}`, getOrgId());
    if (r.ok) {
      setData(r.data);
      setLatestJobId(jobId.trim());
    } else setErr(r.error.message);
  }, [jobId]);

  useEffect(() => {
    if (!polling || !jobId.trim()) return;
    const t = setInterval(() => void fetchJob(), 3000);
    return () => clearInterval(t);
  }, [polling, jobId, fetchJob]);

  const terminal = data?.status && ["complete", "failed", "cancelled"].includes(data.status);
  const pct = data?.progress_percent ?? 0;

  return (
    <div className="space-y-10">
      <header className="max-w-2xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Pipeline</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">Jobs</h1>
        <p className="text-sm leading-relaxed text-zinc-500">
          Look up a job by ID to see stage, progress, and processing minutes. The latest ID from this browser is filled
          in when you create a job from Upload.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[min(100%,280px)] flex-1">
          <label htmlFor="jobId" className="text-sm font-medium text-zinc-300">
            Job ID
          </label>
          <input
            id="jobId"
            name="jobId"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            className="mt-2 block w-full rounded-xl border border-surface-border bg-surface px-3 py-2.5 font-mono text-sm text-zinc-100"
            placeholder="job_…"
            autoComplete="off"
          />
        </div>
        <button
          type="button"
          onClick={() => void fetchJob()}
          className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-surface hover:bg-accent/90"
        >
          Load status
        </button>
        <label className="flex items-center gap-2 rounded-xl border border-surface-border px-3 py-2 text-sm text-zinc-400">
          <input type="checkbox" checked={polling} onChange={(e) => setPolling(e.target.checked)} disabled={!jobId} />
          Auto-refresh (3s)
        </label>
      </div>

      {err ? (
        <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-red-200">
          {err}
        </p>
      ) : null}

      {data ? (
        <article className="rounded-2xl border border-surface-border bg-surface-raised/45 p-6 md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-mono text-sm text-zinc-500">{data.job_id}</p>
              <p className="mt-1 text-lg font-medium text-zinc-100">{data.current_stage || "Processing"}</p>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
                data.status === "complete"
                  ? "bg-accent/20 text-accent"
                  : data.status === "failed"
                    ? "bg-danger/20 text-red-300"
                    : "bg-warn/15 text-amber-200"
              }`}
            >
              {data.status}
            </span>
          </div>

          <div className="mt-6">
            <div className="flex items-baseline justify-between text-sm text-zinc-500">
              <span>Progress</span>
              <span className="font-mono text-zinc-300">{pct}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-border">
              <div
                className={`h-full rounded-full transition-all ${
                  data.status === "failed" ? "bg-danger/80" : "bg-accent"
                }`}
                style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
              />
            </div>
          </div>

          <dl className="mt-8 grid gap-4 text-sm sm:grid-cols-3">
            <div className="rounded-xl border border-surface-border/60 bg-surface/30 p-4">
              <dt className="text-xs uppercase tracking-wide text-zinc-500">Estimated (minutes)</dt>
              <dd className="mt-1 font-mono text-lg text-zinc-100">
                {data.estimated_processing_minutes ?? data.estimated_credits ?? "—"}
              </dd>
            </div>
            <div className="rounded-xl border border-surface-border/60 bg-surface/30 p-4">
              <dt className="text-xs uppercase tracking-wide text-zinc-500">Reserved (minutes)</dt>
              <dd className="mt-1 font-mono text-lg text-zinc-100">
                {data.reserved_processing_minutes ?? data.reserved_credits ?? "—"}
              </dd>
            </div>
            <div className="rounded-xl border border-surface-border/60 bg-surface/30 p-4">
              <dt className="text-xs uppercase tracking-wide text-zinc-500">Used so far (minutes)</dt>
              <dd className="mt-1 font-mono text-lg text-zinc-100">
                {data.processing_minutes_used_so_far ?? data.actual_credits_so_far ?? "—"}
              </dd>
            </div>
          </dl>

          {terminal ? (
            <p className="mt-6 text-sm text-zinc-500">
              This run has finished.{" "}
              <Link href="/outputs" className="font-medium text-accent no-underline hover:underline">
                View outputs →
              </Link>
            </p>
          ) : null}
        </article>
      ) : null}

      <DebugPanel title="GET /v1/jobs/{id}" json={data ?? { jobId: jobId || null }} />
    </div>
  );
}
