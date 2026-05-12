"use client";

import { useEffect, useState } from "react";
import { browserGet } from "@/lib/client/api";
import { getLatestJobId, getOrgId } from "@/lib/org-storage";
import type { JobOutputsResponse } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";

export default function OutputsPage() {
  const [jobId, setJobId] = useState("");
  const [data, setData] = useState<JobOutputsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setJobId(getLatestJobId() || "");
  }, []);

  const load = async () => {
    if (!jobId.trim()) return;
    setErr(null);
    const r = await browserGet<JobOutputsResponse>(
      `/v1/jobs/${encodeURIComponent(jobId.trim())}/outputs`,
      getOrgId(),
    );
    if (r.ok) setData(r.data);
    else setErr(r.error.message);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-zinc-50">Outputs</h1>
      <p className="max-w-2xl text-sm text-zinc-400">Signed download links from the processing pipeline.</p>
      <div className="flex flex-wrap gap-3">
        <input
          aria-label="Job id"
          value={jobId}
          onChange={(e) => setJobId(e.target.value)}
          className="min-w-[240px] flex-1 rounded-md border border-surface-border bg-surface px-3 py-2 font-mono text-sm text-zinc-100 md:max-w-md"
          placeholder="job_…"
        />
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface hover:bg-accent/90"
        >
          Load outputs
        </button>
      </div>
      {err ? <p className="text-sm text-danger">{err}</p> : null}
      {data && data.outputs.length === 0 ? (
        <p className="rounded-lg border border-warn/30 bg-warn/10 px-4 py-3 text-sm text-amber-100">
          Outputs are not ready yet — wait for the job to complete, then retry.
        </p>
      ) : null}
      {data && data.outputs.length > 0 ? (
        <ul className="space-y-3">
          {data.outputs.map((o) => (
            <li key={o.type + o.title} className="rounded-lg border border-surface-border bg-surface-raised/40 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium text-zinc-100">{o.title}</p>
                  <p className="text-xs text-zinc-500">
                    {o.type} · {o.format}
                  </p>
                </div>
                <a
                  href={o.download_url}
                  className="rounded-md bg-surface-border px-3 py-1.5 text-sm text-zinc-100 no-underline hover:bg-surface-border/80"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open / download
                </a>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      <DebugPanel title="GET /v1/jobs/{id}/outputs" json={data} />
    </div>
  );
}
