"use client";

import { useCallback, useEffect, useState } from "react";
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

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-zinc-50">Jobs</h1>
      <p className="max-w-2xl text-sm text-zinc-400">
        There is no list endpoint yet — load by job id. The latest id from this browser is pre-filled when you create a
        job from Upload.
      </p>
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
        <div className="rounded-xl border border-surface-border bg-surface-raised/40 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-mono text-sm text-zinc-400">{data.job_id}</p>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                data.status === "complete"
                  ? "bg-accent/20 text-accent"
                  : data.status === "failed"
                    ? "bg-danger/20 text-danger"
                    : "bg-warn/20 text-warn"
              }`}
            >
              {data.status}
            </span>
          </div>
          <p className="mt-3 text-2xl font-semibold text-zinc-100">{data.progress_percent}%</p>
          <p className="text-sm text-zinc-400">{data.current_stage}</p>
          <dl className="mt-4 grid gap-2 text-sm text-zinc-300 sm:grid-cols-3">
            <div>
              <dt className="text-zinc-500">Estimated</dt>
              <dd>{data.estimated_credits ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Reserved</dt>
              <dd>{data.reserved_credits ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Actual so far</dt>
              <dd>{data.actual_credits_so_far ?? "—"}</dd>
            </div>
          </dl>
          {terminal ? (
            <p className="mt-4 text-sm text-zinc-400">
              Terminal state reached.{" "}
              <a href="/outputs" className="text-accent">
                View outputs →
              </a>
            </p>
          ) : null}
        </div>
      ) : null}
      <DebugPanel title="GET /v1/jobs/{id}" json={data ?? { jobId }} />
    </div>
  );
}
