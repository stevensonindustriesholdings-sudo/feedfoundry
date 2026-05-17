"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { browserGet, browserPost } from "@/lib/client/api";
import { getOrgId, setLatestJobId } from "@/lib/org-storage";
import type {
  CreateJobResponse,
  CompleteUploadResponse,
  JobOutputsResponse,
  JobStatusResponse,
  PresignUploadResponse,
  YoutubeQueueEnqueueResponse,
} from "@/lib/types";
import { OUTPUT_OPTIONS } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";
import type { ClientError } from "@/lib/errors";
import { formatApiUnitsAsProcessing, jobEstimateMinutes } from "@/lib/processing-display";

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
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [youtubeMsg, setYoutubeMsg] = useState<string | null>(null);
  const [youtubeErr, setYoutubeErr] = useState<string | null>(null);
  const [youtubeBusy, setYoutubeBusy] = useState(false);

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
    setStatus("Preparing secure upload…");
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
      setError(pr.error);
      setStatus("Could not start upload.");
      setDebug(pr.error);
      return;
    }
    setPresign(pr.data);
    setStatus("Uploading to your archive storage…");

    try {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", pr.data.upload_url);
      const putContentType = file.type || "application/octet-stream";
      xhr.setRequestHeader("Content-Type", putContentType);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) setUploadPct(Math.round((100 * e.loaded) / e.total));
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

    setStatus("Confirming upload with API…");
    const complete = await browserPost<CompleteUploadResponse>(
      "/v1/uploads/complete",
      { media_asset_id: pr.data.media_asset_id },
      getOrgId(),
    );
    if (!complete.ok) {
      setError(complete.error);
      setStatus("Upload reached storage but completion call failed.");
      setDebug((prev) => ({
        ...(prev ?? {}),
        completeError: complete.error,
      }));
      return;
    }
    setDebug((prev) => ({ ...(prev ?? {}), complete: complete.data }));

    if (!confirmJob) {
      setStatus("Media received and registered. Enable job confirmation below to reserve processing time and queue work.");
      return;
    }

    setStatus("Creating processing job…");
    const jr = await browserPost<CreateJobResponse>(
      "/v1/jobs",
      { media_asset_id: pr.data.media_asset_id, requested_outputs: outputs },
      getOrgId(),
    );
    if (!jr.ok) {
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
    setStatus("Job queued — watching pipeline below.");
    setDebug({ presign: pr.data, job: jr.data });
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
      const done = ["completed", "failed", "cancelled"].includes(jr.data.status);
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

  const queueYoutubeUrl = useCallback(async () => {
    setYoutubeErr(null);
    setYoutubeMsg(null);
    const u = youtubeUrl.trim();
    if (!u) {
      setYoutubeErr("Paste a public YouTube watch or Shorts URL.");
      return;
    }
    setYoutubeBusy(true);
    const r = await browserPost<YoutubeQueueEnqueueResponse>("/v1/youtube-source-queue", { youtube_url: u }, getOrgId());
    setYoutubeBusy(false);
    if (!r.ok) {
      setYoutubeErr(r.error.message);
      return;
    }
    setYoutubeMsg(`Queued backlog id ${r.data.id} — no download started.`);
    setYoutubeUrl("");
  }, [youtubeUrl]);

  return (
    <div className="space-y-10">
      {isLocal ? (
        <div className="max-w-3xl rounded-2xl border border-accent/25 bg-accent/5 px-5 py-4 text-sm text-zinc-300">
          <strong className="text-zinc-100">Local dev</strong> — this UI talks to your FeedFoundry API through{" "}
          <code className="rounded bg-surface px-1 py-0.5 text-xs text-accent">/api/ff</code>. Set{" "}
          <code className="rounded bg-surface px-1 py-0.5 text-xs">FEEDFOUNDRY_API_BASE_URL</code> and{" "}
          <code className="rounded bg-surface px-1 py-0.5 text-xs">FEEDFOUNDRY_INTERNAL_API_KEY</code> in{" "}
          <code className="rounded bg-surface px-1 py-0.5 text-xs">apps/web/.env.local</code>, then{" "}
          <code className="rounded bg-surface px-1 py-0.5 text-xs">npm run dev</code> here (port 3000).
        </div>
      ) : null}

      <header className="max-w-2xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Creator ingest</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">Upload video or audio</h1>
        <p className="text-sm leading-relaxed text-zinc-500">
          Bring files from your own library (no link scraping). We store them in your archive bucket, then optionally run
          a processing job. Confirming a job reserves{" "}
          <strong className="font-medium text-zinc-400">processing time</strong> up front so work never starts without
          allowance.
        </p>
        <p className="text-sm leading-relaxed text-zinc-500">
          Optional: queue a <strong className="font-medium text-zinc-400">public YouTube URL</strong> for a future
          pipeline — we only record the link today (no ingestion, no auth bypass).
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
              className="mt-2 block w-full text-sm text-zinc-300 file:mr-4 file:rounded-lg file:border-0 file:bg-surface-border file:px-4 file:py-2 file:font-medium file:text-zinc-100"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
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
              I confirm that creating a processing job will{" "}
              <strong className="text-zinc-300">reserve processing time</strong> for this run (released or settled when
              the job finishes).
            </span>
          </label>
          <div className="rounded-xl border border-surface-border/60 bg-surface/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">YouTube URL backlog</p>
            <label htmlFor="yturl" className="mt-2 block text-sm font-medium text-zinc-300">
              Public YouTube URL (enqueue only)
            </label>
            <input
              id="yturl"
              type="url"
              placeholder="https://www.youtube.com/watch?v=…"
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              className="mt-2 w-full rounded-xl border border-surface-border bg-surface px-3 py-2.5 text-sm text-zinc-100"
            />
            <button
              type="button"
              disabled={youtubeBusy}
              onClick={() => void queueYoutubeUrl()}
              className="mt-3 w-full rounded-lg border border-accent/40 bg-surface px-4 py-2 text-sm font-medium text-accent hover:bg-accent/10 disabled:opacity-50 sm:w-auto"
            >
              {youtubeBusy ? "Queueing…" : "Queue URL (no download)"}
            </button>
            {youtubeErr ? (
              <p className="mt-2 text-xs text-red-300" role="alert">
                {youtubeErr}
              </p>
            ) : null}
            {youtubeMsg ? (
              <p className="mt-2 text-xs text-emerald-300" aria-live="polite">
                {youtubeMsg}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => void runUpload()}
            className="w-full rounded-xl bg-accent py-3 text-sm font-semibold text-surface hover:bg-accent/90 sm:w-auto sm:px-8"
          >
            {confirmJob ? "Upload and start job" : "Upload only"}
          </button>
          <p className="text-sm text-zinc-500" aria-live="polite">
            {status}
          </p>
          {uploadPct !== null ? (
            <div className="space-y-1">
              <div className="h-1.5 overflow-hidden rounded-full bg-surface-border">
                <div
                  className="h-full rounded-full bg-accent transition-all duration-300"
                  style={{ width: `${uploadPct}%` }}
                />
              </div>
              <p className="text-xs text-zinc-600">{uploadPct}% transferred</p>
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
                Estimated {formatApiUnitsAsProcessing(jobEstimateMinutes(job.estimated_processing_minutes, job.estimated_credits))}{" "}
                · Reserved{" "}
                {formatApiUnitsAsProcessing(jobEstimateMinutes(job.reserved_processing_minutes, job.reserved_credits))}
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
              ) : liveJob.status === "completed" ? (
                <p className="mt-3 text-xs text-zinc-500">Waiting for output links…</p>
              ) : null}
            </div>
          ) : null}
          <p className="text-xs leading-relaxed text-zinc-600">
            Early access: enrichments and bundles may expand over time. Annual hosted archive access and processing-time
            rules follow the active product policy.
          </p>
        </div>
      </div>

      <DebugPanel title="Upload flow response" json={debug ?? { note: "Run an upload to capture responses here." }} />
    </div>
  );
}
