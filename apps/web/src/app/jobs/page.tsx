"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { browserGet } from "@/lib/client/api";
import { getLatestJobId, getOrgId, setLatestJobId } from "@/lib/org-storage";
import type { JobStatusResponse } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";
import { formatApiUnitsAsProcessing } from "@/lib/processing-display";

const PIPELINE_HINT = ["Queued", "Estimating & reserving", "Processing", "Complete"] as const;

function humanizeStatus(status: string): string {
  const s = status.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

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
  const stageLabel = data?.current_stage?.trim() || "—";

  return (
    <div className="space-y-8">
      <header className="max-w-2xl space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Pipeline</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50">Processing status</h1>
        <p className="text-sm leading-relaxed text-zinc-400">
          Track a single job by ID. There is no list endpoint yet —{" "}
          <span className="font-mono text-zinc-500">GET /v1/jobs?org=…</span> TODO(api-contract). The latest ID from
          this browser is pre-filled after you create a job from Upload.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="jobId" className="text-sm font-medium text-zinc-300">
            Job ID
          </label>
          <input
            id="jobId"
            name="jobId"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            className="mt-1 block w-full min-w-[240px] rounded-md border border-surface-border bg-surface px-3 py-2 font-mono text-sm text-zinc-100 md:w-96"
            placeholder="job_…"
            autoComplete="off"
          />
        </div>
        <button
          type="button"
          onClick={() => void fetchJob()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface hover:bg-accent/90"
        >
          Load status
        </button>
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input type="checkbox" checked={polling} onChange={(e) => setPolling(e.target.checked)} disabled={!jobId} />
          Poll every 3s
        </label>
      </div>
      {err ? (
        <p role="alert" className="text-sm text-danger">
          {err}
        </p>
      ) : null}
      {data ? (
        <div className="space-y-5">
          <div className="rounded-xl border border-surface-border bg-surface-raised/40 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-sm text-zinc-400">{data.job_id}</p>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  data.status === "complete"
                    ? "bg-accent/20 text-accent"
                    : data.status === "failed"
                      ? "bg-danger/20 text-danger"
                      : data.status === "cancelled"
                        ? "bg-zinc-700 text-zinc-300"
                        : "bg-warn/20 text-warn"
                }`}
              >
                {humanizeStatus(data.status)}
              </span>
            </div>

            <div className="mt-5">
              <div className="flex items-baseline justify-between text-xs text-zinc-500">
                <span>Progress</span>
                <span className="font-mono text-zinc-300">{data.progress_percent}%</span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-border">
                <div
                  className={`h-full rounded-full transition-all ${
                    data.status === "failed" ? "bg-danger/80" : "bg-accent"
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, data.progress_percent))}%` }}
                />
              </div>
            </div>

            <p className="mt-4 text-sm text-zinc-300">
              Current stage: <span className="text-zinc-100">{stageLabel}</span>
            </p>

            <dl className="mt-4 grid gap-3 text-sm text-zinc-300 sm:grid-cols-3">
              <div className="rounded-lg border border-surface-border/60 bg-surface/40 p-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">Estimated time</dt>
                <dd className="mt-1 font-medium text-zinc-100">{formatApiUnitsAsProcessing(data.estimated_credits)}</dd>
              </div>
              <div className="rounded-lg border border-surface-border/60 bg-surface/40 p-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">Reserved for job</dt>
                <dd className="mt-1 font-medium text-zinc-100">{formatApiUnitsAsProcessing(data.reserved_credits)}</dd>
              </div>
              <div className="rounded-lg border border-surface-border/60 bg-surface/40 p-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">Used so far</dt>
                <dd className="mt-1 font-medium text-zinc-100">{formatApiUnitsAsProcessing(data.actual_credits_so_far)}</dd>
              </div>
            </dl>

            {data.status === "failed" ? (
              <div
                role="status"
                className="mt-5 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-red-100"
              >
                <p className="font-medium text-red-50">This run did not complete</p>
                <p className="mt-2 text-red-100/90">
                  Failed jobs should not bill you for a full successful run: reserved processing time is released on
                  failure per server ledger rules (see ledger tests in the API repo). Your dashboard totals
                  should reflect the settlement after the job ends.
                </p>
                {data.failure_message ? (
                  <p className="mt-2 font-mono text-xs text-red-200/90">{data.failure_message}</p>
                ) : (
                  <p className="mt-2 text-xs text-red-200/80">
                    TODO(api-contract): extend <span className="font-mono">GET /v1/jobs/{"{id}"}</span> with{" "}
                    <span className="font-mono">failure_message</span> / debit summary so this panel can quote the
                    server exactly.
                  </p>
                )}
              </div>
            ) : null}

            {terminal && data.status === "complete" ? (
              <p className="mt-4 text-sm text-zinc-400">
                Processing finished.{" "}
                <Link href="/outputs" className="font-medium text-accent no-underline hover:underline">
                  View outputs →
                </Link>
              </p>
            ) : null}
            {terminal && data.status !== "complete" ? (
              <p className="mt-4 text-sm text-zinc-400">
                <Link href="/upload" className="text-accent no-underline hover:underline">
                  Upload again
                </Link>{" "}
                or adjust inputs and retry.
              </p>
            ) : null}
          </div>

          <ol className="flex flex-wrap gap-4 text-xs text-zinc-500">
            {PIPELINE_HINT.map((label) => (
              <li key={label} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-accent/60" />
                {label}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      <DebugPanel title="GET /v1/jobs/{id}" json={data ?? { jobId }} />
    </div>
  );
}
