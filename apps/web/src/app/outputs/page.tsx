"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
    <div className="space-y-10">
      <header className="max-w-2xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Deliverables</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">Outputs</h1>
        <p className="text-sm leading-relaxed text-zinc-500">
          Signed links to files produced for a completed job—transcripts, chapters, bundles, and other artefacts for
          your <strong className="font-medium text-zinc-400">creator archive</strong>.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[min(100%,280px)] flex-1">
          <label htmlFor="jobIdOut" className="text-sm font-medium text-zinc-300">
            Job ID
          </label>
          <input
            id="jobIdOut"
            aria-label="Job id"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            className="mt-2 block w-full rounded-xl border border-surface-border bg-surface px-3 py-2.5 font-mono text-sm text-zinc-100"
            placeholder="job_…"
          />
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-surface hover:bg-accent/90"
        >
          Load outputs
        </button>
        <Link
          href="/jobs"
          className="rounded-xl border border-surface-border px-4 py-2.5 text-sm font-medium text-zinc-300 no-underline hover:bg-surface-raised"
        >
          Jobs
        </Link>
      </div>

      {err ? (
        <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-red-200">
          {err}
        </p>
      ) : null}

      {data && data.outputs.length === 0 ? (
        <p className="rounded-2xl border border-warn/25 bg-warn/10 px-5 py-4 text-sm text-amber-100">
          Nothing to download yet—wait until the job completes, then load again.
        </p>
      ) : null}

      {data && data.outputs.length > 0 ? (
        <ul className="grid gap-4 md:grid-cols-2">
          {data.outputs.map((o) => (
            <li
              key={o.type + o.title}
              className="flex flex-col justify-between rounded-2xl border border-surface-border bg-surface-raised/45 p-5"
            >
              <div>
                <p className="font-semibold text-zinc-100">{o.title}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  {o.type} · {o.format}
                </p>
              </div>
              <a
                href={o.download_url}
                className="mt-5 inline-flex w-fit items-center justify-center rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-surface no-underline hover:bg-accent/90"
                target="_blank"
                rel="noreferrer"
              >
                Download
              </a>
            </li>
          ))}
        </ul>
      ) : null}

      <DebugPanel title="GET /v1/jobs/{id}/outputs" json={data} />
    </div>
  );
}
