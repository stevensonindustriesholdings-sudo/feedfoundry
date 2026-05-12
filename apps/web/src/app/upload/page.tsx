"use client";

import { useCallback, useState } from "react";
import { browserPost } from "@/lib/client/api";
import { getOrgId, setLatestJobId } from "@/lib/org-storage";
import type { CreateJobResponse, PresignUploadResponse } from "@/lib/types";
import { OUTPUT_OPTIONS } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";
import { StagingLimitations } from "@/components/StagingLimitations";
import type { ClientError } from "@/lib/errors";

const defaultOutputs = ["transcript", "chapters", "metadata", "hosted_manifest"];

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [mediaType, setMediaType] = useState("video");
  const [outputs, setOutputs] = useState<string[]>(defaultOutputs);
  const [confirmJob, setConfirmJob] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<ClientError | null>(null);
  const [presign, setPresign] = useState<PresignUploadResponse | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [job, setJob] = useState<CreateJobResponse | null>(null);
  const [debug, setDebug] = useState<unknown>(null);

  const toggleOutput = (id: string) => {
    setOutputs((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const runUpload = useCallback(async () => {
    setError(null);
    setJob(null);
    setPresign(null);
    setUploadPct(null);
    setDebug(null);
    if (!file) {
      setStatus("Choose a file first.");
      return;
    }
    setStatus("Requesting presign…");
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
      setStatus("Presign failed.");
      setDebug(pr.error);
      return;
    }
    setPresign(pr.data);
    setStatus("Uploading to storage…");

    try {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", pr.data.upload_url);
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
      setStatus("Upload to signed URL failed.");
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
    setStatus("Uploaded. Create processing job?");
    setDebug({ presign: pr.data, uploaded: true });

    if (!confirmJob) {
      setStatus("Uploaded. Enable “Confirm job creation” to reserve credits and queue processing.");
      return;
    }

    setStatus("Creating job…");
    const jr = await browserPost<CreateJobResponse>(
      "/v1/jobs",
      { media_asset_id: pr.data.media_asset_id, requested_outputs: outputs },
      getOrgId(),
    );
    if (!jr.ok) {
      setError(jr.error);
      setStatus("Job creation failed.");
      setDebug((prev) => ({ ...(typeof prev === "object" && prev ? prev : {}), jobError: jr.error }));
      return;
    }
    setJob(jr.data);
    setLatestJobId(jr.data.job_id);
    setStatus("Job queued.");
    setDebug({ presign: pr.data, job: jr.data });
  }, [file, mediaType, outputs, confirmJob]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-50">Upload</h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          Presign → PUT to signed URL → optional job creation (reserves processing credits). Confirm before creating a
          job.
        </p>
      </div>

      <StagingLimitations />

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-4 rounded-xl border border-surface-border bg-surface-raised/40 p-5">
          <div>
            <label htmlFor="file" className="text-sm font-medium text-zinc-300">
              Media file
            </label>
            <input
              id="file"
              name="file"
              type="file"
              className="mt-1 block w-full text-sm text-zinc-300 file:mr-3 file:rounded-md file:border-0 file:bg-surface-border file:px-3 file:py-1.5 file:text-zinc-100"
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
              className="mt-1 w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-zinc-100"
              value={mediaType}
              onChange={(e) => setMediaType(e.target.value)}
            >
              <option value="video">video</option>
              <option value="audio">audio</option>
            </select>
          </div>
          <fieldset>
            <legend className="text-sm font-medium text-zinc-300">Requested outputs</legend>
            <ul className="mt-2 grid gap-2 sm:grid-cols-2">
              {OUTPUT_OPTIONS.map((o) => (
                <li key={o.id}>
                  <label className="flex items-center gap-2 text-sm text-zinc-300">
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
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={confirmJob} onChange={(e) => setConfirmJob(e.target.checked)} />
            I confirm creating a processing job will reserve credits.
          </label>
          <button
            type="button"
            onClick={() => void runUpload()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface hover:bg-accent/90"
          >
            Run presign + upload{confirmJob ? " + job" : ""}
          </button>
          <p className="text-sm text-zinc-500" aria-live="polite">
            {status}
          </p>
          {uploadPct !== null ? <p className="text-xs text-zinc-400">Upload progress: {uploadPct}%</p> : null}
        </div>

        <div className="space-y-4">
          {error ? (
            <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-red-100">
              {error.message}
            </div>
          ) : null}
          {presign ? (
            <div className="rounded-xl border border-surface-border bg-surface-raised/40 p-4 text-sm text-zinc-300">
              <p>
                <span className="text-zinc-500">media_asset_id:</span> {presign.media_asset_id}
              </p>
              <p className="mt-1 text-xs break-all text-zinc-500">storage_key: {presign.storage_key}</p>
            </div>
          ) : null}
          {job ? (
            <div className="rounded-xl border border-accent/40 bg-accent/10 p-4 text-sm text-zinc-100">
              <p className="font-medium">Job created</p>
              <p className="mt-1">job_id: {job.job_id}</p>
              <p>
                estimated_credits: {job.estimated_credits} · reserved: {job.reserved_credits}
              </p>
              <a href="/jobs" className="mt-2 inline-block text-accent">
                Open Jobs →
              </a>
            </div>
          ) : null}
        </div>
      </div>

      <DebugPanel title="Upload flow" json={debug ?? { note: "no debug payload yet" }} />
    </div>
  );
}
