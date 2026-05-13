"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { browserGet, browserPost } from "@/lib/client/api";
import { getOrgId, setLatestJobId } from "@/lib/org-storage";
import type { CreateJobResponse, JobOutputsResponse, JobStatusResponse, PresignUploadResponse } from "@/lib/types";
import { OUTPUT_OPTIONS } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";
import type { ClientError } from "@/lib/errors";

type DebugState = Record<string, unknown>;

const defaultOutputs = ["transcript", "chapters", "metadata", "hosted_manifest"];

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [mediaType, setMediaType] = useState("video");
  const [outputs, setOutputs] = useState<string[]>(defaultOutputs);
  const [confirmJob, setConfirmJob] = useState(true);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<ClientError | null>(null);
  const [presign, setPresign] = useState<PresignUploadResponse | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [job, setJob] = useState<CreateJobResponse | null>(null);
  const [debug, setDebug] = useState<DebugState | null>(null);
  const [liveJob, setLiveJob] = useState<JobStatusResponse | null>(null);
  const [liveOutputs, setLiveOutputs] = useState<JobOutputsResponse | null>(null);
  const [livePollErr, setLivePollErr] = useState<string | null>(null);
  const [isLocal, setIsLocal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState<string>("");

  const toggleOutput = (id: string) => {
    setOutputs((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const runUpload = useCallback(async () => {
    setError(null);
    setJob(null);
    setLiveJob(null);
    setLiveOutputs(null);
    setLivePollErr(null);
    setPresign(null);
    setUploadPct(null);
    setDebug(null);
    if (!file) {
      setStatus("Choose a media file to continue.");
      return;
    }
    setBusy(true);
    setUploadPct(-2);
    try {
    setStatus("Step 1/3 — asking API for a signed upload URL…");
    const pr = await browserPost<PresignUploadResponse>(
      "/v1/uploads/presign",
      {
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        file_size_bytes: file.size,
        media_type: mediaType,
      },
      getOrgId(),
    );
    if (!pr.ok) {
      setUploadPct(null);
      setError(pr.error);
      setStatus("Could not start upload.");
      setDebug(pr.error);
      return;
    }
    setPresign(pr.data);
    setStatus("Step 2/3 — uploading bytes to storage (keep this tab open)…");
    setUploadPct(0);

    try {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", pr.data.upload_url);
      const putContentType = file.type || "application/octet-stream";
      xhr.setRequestHeader("Content-Type", putContentType);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && e.total > 0) {
          setUploadPct(Math.round((100 * e.loaded) / e.total));
        } else if (file.size > 0) {
          setUploadPct(Math.min(99, Math.round((100 * e.loaded) / file.size)));
        } else {
          setUploadPct((p) => (p !== null && p < 0 ? p : -1));
        }
      };
      await new Promise<void>((resolve, reject) => {
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) resolve();
          else reject(new Error(`Upload HTTP ${xhr.status}`));
        };
        xhr.onerror = () => reject(new Error("Network error during upload"));
        xhr.send(file);
      });
    } catch (e) {
      setUploadPct(null);
      setStatus("Upload did not complete.");
      setError({
        code: "upstream_error",
        status: 0,
        message: (e as Error).message,
        detail: "upload_failed",
      });
      setDebug({ presign: pr.data, error: String(e) });
      return;
    }

    setUploadPct(100);
    setDebug({ presign: pr.data, uploaded: true });

    if (!confirmJob) {
      setStatus("Media received. Enable job confirmation below to reserve processing time and queue work.");
      return;
    }

    setStatus("Step 3/3 — creating processing job…");
    const jr = await browserPost<CreateJobResponse>(
      "/v1/jobs",
      { media_asset_id: pr.data.media_asset_id, requested_outputs: outputs },
      getOrgId(),
    );
    if (!jr.ok) {
      setUploadPct(null);
      setError(jr.error);
      setStatus("Job could not be created.");
      setDebug((prev) => ({
        ...(prev ?? {}),
        jobError: jr.error,
      }));
      return;
    }
    setJob(jr.data);
    setLatestJobId(jr.data.job_id);
    if (jr.data.warning && jr.data.message) {
      setStatus(`${jr.data.message} Watching pipeline below.`);
    } else {
      setStatus("Job queued — watching pipeline below.");
    }
    setDebug({ presign: pr.data, job: jr.data });
    } finally {
      setBusy(false);
    }
  }, [file, mediaType, outputs, confirmJob]);

  useEffect(() => {
    const h = window.location.hostname;
    setIsLocal(h === "localhost" || h === "127.0.0.1");
  }, []);

  useEffect(() => {
    const id = job?.job_id;
    if (!id) return;
    let cancelled = false;
    const tick = async () => {
      const jr = await browserGet<JobStatusResponse>(`/v1/jobs/${encodeURIComponent(id)}`, getOrgId());
      if (cancelled) return;
      if (!jr.ok) {
        setLivePollErr(jr.error.message);
        return;
      }
      setLivePollErr(null);
      setLiveJob(jr.data);
      const done = ["complete", "failed", "cancelled"].includes(jr.data.status);
      if (done) {
        const or = await browserGet<JobOutputsResponse>(`/v1/jobs/${encodeURIComponent(id)}/outputs`, getOrgId());
        if (!cancelled && or.ok) setLiveOutputs(or.data);
      }
    };
    void tick();
    const iv = setInterval(() => void tick(), 2000);
    return () => {
      cancelled = true;
      clearInterval(iv);
    };
  }, [job?.job_id]);

  return (
    <div className="space-y-10">
      {isLocal ? (
        <div className="max-w-3xl rounded-2xl border border-accent/25 bg-accent/5 px-5 py-4 text-sm text-zinc-300">
          <strong className="text-zinc-100">Local</strong> — browser calls go through this app&apos;s{" "}
          <code className="rounded bg-surface px-1 py-0.5 text-xs text-accent">/api/ff</code> proxy to your FeedFoundry
          API.
        </div>
      ) : null}

      <header className="max-w-2xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Ingest</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">Upload</h1>
        <p className="text-sm leading-relaxed text-zinc-500">
          Send media to your creator archive storage, then optionally create a job. Job creation reserves{" "}
          <strong className="font-medium text-zinc-400">processing minutes</strong> against your account.
        </p>
      </header>

      <ol className="flex flex-wrap gap-4 text-xs font-medium text-zinc-500 md:gap-8">
        {["1 · Prepare", "2 · Transfer", "3 · Process"].map((label, i) => (
          <li key={label} className="flex items-center gap-2">
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full text-[11px] ${
                i === 0 ? "bg-accent/20 text-accent" : "bg-surface-border/60 text-zinc-500"
              }`}
            >
              {i + 1}
            </span>
            {label.replace(/^\d · /, "")}
          </li>
        ))}
      </ol>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-5 rounded-2xl border border-surface-border bg-surface-raised/40 p-6 md:p-7">
          <div>
            <label htmlFor="file" className="text-sm font-medium text-zinc-300">
              Media file
            </label>
            <input
              id="file"
              name="file"
              type="file"
              accept="video/*,audio/*"
              className="mt-2 block w-full text-sm text-zinc-300 file:mr-4 file:rounded-lg file:border-0 file:bg-surface-border file:px-4 file:py-2 file:font-medium file:text-zinc-100"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setFile(f);
                if (f) {
                  const mb = (f.size / (1024 * 1024)).toFixed(1);
                  setSelectedLabel(`${f.name} · ${mb} MiB`);
                  setStatus(`Selected “${f.name}”. Click “Upload and start job” below — choosing a file alone does not upload.`);
                } else {
                  setSelectedLabel("");
                  setStatus("");
                }
              }}
            />
            {selectedLabel ? (
              <p className="mt-2 text-xs text-zinc-500">
                <span className="font-medium text-zinc-400">Ready:</span> {selectedLabel}
              </p>
            ) : null}
          </div>
          <div>
            <label htmlFor="mediaType" className="text-sm font-medium text-zinc-300">
              Media type
            </label>
            <select
              id="mediaType"
              name="mediaType"
              className="mt-2 w-full rounded-xl border border-surface-border bg-surface px-3 py-2.5 text-sm text-zinc-100"
              value={mediaType}
              onChange={(e) => setMediaType(e.target.value)}
            >
              <option value="video">Video</option>
              <option value="audio">Audio</option>
            </select>
          </div>
          <fieldset>
            <legend className="text-sm font-medium text-zinc-300">Outputs to generate</legend>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {OUTPUT_OPTIONS.map((o) => (
                <li key={o.id}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-transparent px-2 py-1.5 text-sm text-zinc-400 hover:border-surface-border hover:bg-surface/50">
                    <input
                      type="checkbox"
                      checked={outputs.includes(o.id)}
                      onChange={() => toggleOutput(o.id)}
                      className="rounded border-surface-border"
                    />
                    {o.label}
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-surface-border/80 bg-surface/30 p-4 text-sm text-zinc-400">
            <input
              type="checkbox"
              checked={confirmJob}
              onChange={(e) => setConfirmJob(e.target.checked)}
              className="mt-0.5 rounded border-surface-border"
            />
            <span>
              I confirm that creating a processing job will <strong className="text-zinc-300">reserve processing minutes</strong>{" "}
              for this run.
            </span>
          </label>
          <button
            type="button"
            disabled={busy || !file}
            onClick={() => void runUpload()}
            className="w-full rounded-xl bg-accent py-3 text-sm font-semibold text-surface hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:px-8"
          >
            {busy ? "Working…" : confirmJob ? "Upload and start job" : "Upload only"}
          </button>
          <p className="text-sm text-zinc-500" aria-live="polite">
            {status}
          </p>
          {uploadPct !== null ? (
            <div
              className="space-y-2 rounded-xl border border-surface-border bg-surface/40 p-4"
              aria-busy={busy && uploadPct >= 0 && uploadPct < 100}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Video upload progress</p>
                {uploadPct >= 0 ? (
                  <span className="font-mono text-xs tabular-nums text-accent">{uploadPct}%</span>
                ) : (
                  <span className="text-xs text-accent">…</span>
                )}
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-surface-border shadow-inner">
                {uploadPct < 0 ? (
                  <div className="h-full w-2/5 rounded-full bg-accent motion-safe:animate-pulse" />
                ) : (
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-accent/90 to-accent transition-[width] duration-200"
                    style={{ width: `${Math.min(100, Math.max(0, uploadPct))}%` }}
                  />
                )}
              </div>
              <p className="text-xs text-zinc-500">
                {uploadPct === -2
                  ? "Getting a secure upload slot from the server…"
                  : uploadPct === -1
                    ? "Sending your file — the browser isn’t reporting exact percent; this bar still tracks bytes when possible."
                    : uploadPct < 100
                      ? "Do not close this tab until the bar reaches 100%."
                      : "File delivered — finishing up."}
              </p>
            </div>
          ) : null}
        </div>

        <div className="space-y-4">
          {error ? (
            <div role="alert" className="rounded-2xl border border-danger/35 bg-danger/10 px-5 py-4 text-sm text-red-100">
              {error.message}
            </div>
          ) : null}
          {presign ? (
            <div className="rounded-2xl border border-surface-border bg-surface-raised/40 p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-accent">Media secured</p>
              <p className="mt-2 text-sm text-zinc-300">
                Asset ID <span className="font-mono text-zinc-100">{presign.media_asset_id}</span>
              </p>
              <p className="mt-3 text-xs text-zinc-600">
                Storage path is managed for you; use Jobs after you queue processing.
              </p>
            </div>
          ) : null}
          {job ? (
            <div className="rounded-2xl border border-accent/30 bg-accent/10 p-5">
              <p className="font-semibold text-zinc-100">Job queued</p>
              <p className="mt-2 font-mono text-sm text-zinc-300">{job.job_id}</p>
              <p className="mt-2 text-sm text-zinc-400">
                Estimated minutes {job.estimated_minutes} · Reserved {job.reserved_credits}
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Link href="/jobs" className="text-sm font-semibold text-accent no-underline hover:underline">
                  Open Jobs →
                </Link>
                <Link href="/outputs" className="text-sm font-medium text-zinc-400 no-underline hover:text-zinc-200">
                  Outputs (when complete) →
                </Link>
              </div>
            </div>
          ) : null}

          {job && liveJob ? (
            <div className="rounded-2xl border border-surface-border bg-surface-raised/50 p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-accent">Live pipeline</p>
              <p className="mt-2 text-sm text-zinc-300">
                <span className="font-mono text-zinc-100">{liveJob.job_id}</span> ·{" "}
                <span className="text-zinc-400">{liveJob.current_stage || "—"}</span>
              </p>
              <div className="mt-3 flex items-baseline justify-between text-xs text-zinc-500">
                <span>Progress</span>
                <span className="font-mono text-zinc-300">{liveJob.progress_percent ?? 0}%</span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-border">
                <div
                  className={`h-full rounded-full ${
                    liveJob.status === "failed" ? "bg-danger/80" : "bg-accent"
                  } transition-all`}
                  style={{ width: `${Math.min(100, Math.max(0, liveJob.progress_percent ?? 0))}%` }}
                />
              </div>
              <p className="mt-3 text-xs uppercase tracking-wide text-zinc-500">Status · {liveJob.status}</p>
              {livePollErr ? (
                <p className="mt-2 text-xs text-red-300" role="alert">
                  {livePollErr}
                </p>
              ) : null}
              {liveOutputs && liveOutputs.outputs.length > 0 ? (
                <div className="mt-4 border-t border-surface-border pt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                    Outputs ({liveOutputs.outputs.length})
                  </p>
                  <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto text-xs text-zinc-400">
                    {liveOutputs.outputs.map((o) => (
                      <li key={o.type}>
                        <a
                          href={o.download_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-accent no-underline hover:underline"
                        >
                          {o.title}
                        </a>{" "}
                        <span className="text-zinc-600">({o.type})</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : liveJob.status === "complete" ? (
                <p className="mt-3 text-xs text-zinc-500">Waiting for output links…</p>
              ) : null}
            </div>
          ) : null}
          <p className="text-xs leading-relaxed text-zinc-600">
            Early access: enrichments and output bundles may expand over time; your annual hosted archive and processing
            behaviour follow the active product policy.
          </p>
        </div>
      </div>

      <DebugPanel title="Upload flow response" json={debug ?? { note: "Run an upload to capture responses here." }} />
    </div>
  );
}
