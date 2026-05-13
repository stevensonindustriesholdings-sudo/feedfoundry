"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { browserGet } from "@/lib/client/api";
import { getLatestJobId, getOrgId } from "@/lib/org-storage";
import type { JobOutputsResponse } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";

const OUTPUT_GUIDE: Record<string, string> = {
  transcript: "Full text for search, subtitles, and LLM context.",
  clean_transcript: "Editor-ready prose without disfluencies.",
  chapters: "Timestamped sections for players and show notes.",
  clip_candidates: "Short-form cut suggestions with timing.",
  show_notes: "Human-readable episode summary and links.",
  metadata: "Titles, tags, and structured fields for CMS and SEO.",
  ctas: "Calls to action extracted for descriptions and landing pages.",
  fact_sheet: "Checkable claims and references for editorial QA.",
  faqs: "Question–answer pairs for help centres and companion pages.",
  hosted_manifest: "Public JSON manifest for the hosted archive (AI- and tool-readable).",
  export_bundle: "Packaged download for backups and downstream workflows.",
};

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
    <div className="space-y-8">
      <header className="max-w-3xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Deliverables</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50">Outputs &amp; exports</h1>
        <p className="text-sm leading-relaxed text-zinc-400">
          Signed URLs for each artefact from the pipeline — transcripts, chapters, fact sheets, FAQs, metadata, CTAs,
          hosted manifest JSON, and export bundles. These files are structured for both humans and downstream tools
          (search, CMS, fine-tuning datasets). Data loads from{" "}
          <span className="font-mono text-zinc-500">GET /v1/jobs/{"{id}"}/outputs</span>.
        </p>
      </header>

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
        <Link
          href="/jobs"
          className="inline-flex items-center rounded-lg border border-surface-border px-4 py-2 text-sm font-medium text-zinc-300 no-underline hover:bg-surface-raised"
        >
          Processing status
        </Link>
      </div>
      {err ? <p className="text-sm text-danger">{err}</p> : null}
      {data && data.outputs.length === 0 ? (
        <p className="rounded-lg border border-warn/30 bg-warn/10 px-4 py-3 text-sm text-amber-100">
          Outputs are not ready yet — wait for the job to complete on the Processing page, then retry.
        </p>
      ) : null}
      {data && data.outputs.length > 0 ? (
        <ul className="space-y-4">
          {data.outputs.map((o) => (
            <li
              key={o.type + o.title}
              className="rounded-xl border border-surface-border bg-surface-raised/40 p-5 transition-colors hover:border-accent/25"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-zinc-100">{o.title}</p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {o.type} · {o.format}
                  </p>
                  <p className="mt-2 text-sm text-zinc-400">
                    {OUTPUT_GUIDE[o.type] ?? "Structured output from the FeedFoundry pipeline."}
                  </p>
                </div>
                <a
                  href={o.download_url}
                  className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface no-underline hover:bg-accent/90"
                  target="_blank"
                  rel="noreferrer"
                >
                  Download
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
