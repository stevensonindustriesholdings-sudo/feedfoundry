"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { browserGet, browserPost } from "@/lib/client/api";
import { getOrgId } from "@/lib/org-storage";
import type {
  AccountProcessingBalanceResponse,
  CreateJobResponse,
  CompleteUploadResponse,
  IntakeYoutubePlaylistResponse,
  IntakeYoutubeVideoResponse,
  JobListResponse,
  JobSummaryItem,
  JobOutputsResponse,
  JobStatusResponse,
  PresignUploadResponse,
  WorkerHintsResponse,
  YoutubeQueueListResponse,
} from "@/lib/types";
import { OUTPUT_OPTIONS } from "@/lib/types";
import type { ClientError } from "@/lib/errors";

const defaultOutputs = ["transcript", "chapters", "metadata", "hosted_manifest", "ctas", "faqs", "export_bundle"];

type JsonPreview = { title: string; data: unknown };
type YoutubeQueueItem = YoutubeQueueListResponse["items"][number];

const YOUTUBE_FOCUS_OUTPUTS = [
  "raw_transcript",
  "clean_transcript",
  "transcript",
  "media_inspection",
  "visual_evidence",
  "agent_bundle",
  "hosted_manifest",
  "export_bundle",
];

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "—";
  const whole = Math.max(0, Math.round(seconds));
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function outputLabel(type: string): string {
  const labels: Record<string, string> = {
    raw_transcript: "Transcript",
    clean_transcript: "Transcript summary",
    transcript: "Transcript",
    media_inspection: "Media inspection",
    visual_evidence: "Visual evidence",
    hosted_manifest: "Hosted manifest",
    agent_bundle: "Agent bundle",
    export_bundle: "Export bundle",
  };
  return labels[type] ?? type;
}

function stringifyPreview(data: unknown): string {
  if (typeof data === "string") return data;
  return JSON.stringify(data, null, 2);
}

function findYoutubeRow(rows: YoutubeQueueItem[] | undefined, selectedJobId: string | null): YoutubeQueueItem | null {
  if (!rows || !selectedJobId) return null;
  return rows.find((row) => row.job_id === selectedJobId) ?? null;
}

function findJobSummary(rows: JobSummaryItem[] | undefined, selectedJobId: string | null): JobSummaryItem | null {
  if (!rows || !selectedJobId) return null;
  return rows.find((row) => row.job_id === selectedJobId) ?? null;
}

function outputExists(outputs: JobOutputsResponse | null, types: string[]): boolean {
  return Boolean(outputs?.outputs.some((output) => types.includes(output.type)));
}

export default function PortalPage() {
  const orgId = useMemo(() => getOrgId(), []);
  const [credits, setCredits] = useState<AccountProcessingBalanceResponse | null>(null);
  const [creditsErr, setCreditsErr] = useState<ClientError | null>(null);

  const [hints, setHints] = useState<WorkerHintsResponse | null>(null);
  const [hintsErr, setHintsErr] = useState<ClientError | null>(null);

  const [orgQueue, setOrgQueue] = useState<YoutubeQueueListResponse | null>(null);
  const [orgQueueErr, setOrgQueueErr] = useState<ClientError | null>(null);

  const [recentJobs, setRecentJobs] = useState<JobListResponse | null>(null);
  const [recentJobsErr, setRecentJobsErr] = useState<ClientError | null>(null);

  const [ytVideoUrl, setYtVideoUrl] = useState("");
  const [ytPlaylistUrl, setYtPlaylistUrl] = useState("");
  const [intakeBusy, setIntakeBusy] = useState(false);
  const [intakeMsg, setIntakeMsg] = useState<string | null>(null);
  const [intakeErr, setIntakeErr] = useState<ClientError | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [uploadErr, setUploadErr] = useState<ClientError | null>(null);

  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<JobStatusResponse | null>(null);
  const [jobOutputs, setJobOutputs] = useState<JobOutputsResponse | null>(null);
  const [detailErr, setDetailErr] = useState<ClientError | null>(null);
  const [jsonPreviews, setJsonPreviews] = useState<JsonPreview[]>([]);

  const refreshCore = useCallback(async () => {
    setCreditsErr(null);
    setHintsErr(null);
    setOrgQueueErr(null);
    setRecentJobsErr(null);
    const [cr, wh, oq, jh] = await Promise.all([
      browserGet<AccountProcessingBalanceResponse>("/v1/account/credits", orgId),
      browserGet<WorkerHintsResponse>("/v1/system/worker-hints", orgId),
      browserGet<YoutubeQueueListResponse>("/v1/youtube-source-queue?limit=30&offset=0", orgId),
      browserGet<JobListResponse>("/v1/jobs?limit=25&offset=0", orgId),
    ]);
    if (cr.ok) setCredits(cr.data);
    else {
      setCredits(null);
      setCreditsErr(cr.error);
    }
    if (wh.ok) setHints(wh.data);
    else {
      setHints(null);
      setHintsErr(wh.error);
    }
    if (oq.ok) setOrgQueue(oq.data);
    else {
      setOrgQueue(null);
      setOrgQueueErr(oq.error);
    }
    if (jh.ok) setRecentJobs(jh.data);
    else {
      setRecentJobs(null);
      setRecentJobsErr(jh.error);
    }
  }, [orgId]);

  useEffect(() => {
    void refreshCore();
  }, [refreshCore]);

  const loadJobDetail = useCallback(
    async (jobId: string) => {
      setSelectedJobId(jobId);
      setDetailErr(null);
      setJobDetail(null);
      setJobOutputs(null);
      setJsonPreviews([]);
      const [st, outs] = await Promise.all([
        browserGet<JobStatusResponse>(`/v1/jobs/${jobId}`, orgId),
        browserGet<JobOutputsResponse>(`/v1/jobs/${jobId}/outputs`, orgId),
      ]);
      if (!st.ok) {
        setDetailErr(st.error);
        return;
      }
      setJobDetail(st.data);
      if (!outs.ok) {
        setDetailErr(outs.error);
        return;
      }
      setJobOutputs(outs.data);
      const want = new Set([
        "hosted_manifest",
        "metadata",
        "ctas",
        "faqs",
        "fact_sheet",
        "export_bundle",
        "media_inspection",
        "visual_evidence",
        "agent_bundle",
        "raw_transcript",
        "clean_transcript",
      ]);
      const previews: JsonPreview[] = [];
      for (const o of outs.data.outputs) {
        if (!want.has(o.type)) continue;
        try {
          const r = await fetch(o.download_url);
          if (!r.ok) continue;
          const data = await r.json();
          previews.push({ title: o.type, data });
        } catch {
          previews.push({ title: o.type, data: "(could not fetch JSON — open download URL)" });
        }
      }
      setJsonPreviews(previews);
    },
    [orgId],
  );

  const submitYoutubeVideo = async () => {
    setIntakeBusy(true);
    setIntakeErr(null);
    setIntakeMsg(null);
    const u = ytVideoUrl.trim();
    if (!u) {
      setIntakeBusy(false);
      setIntakeErr({ code: "bad_request", status: 400, message: "Paste a YouTube watch URL." });
      return;
    }
    const r = await browserPost<IntakeYoutubeVideoResponse>(
      "/v1/intake/youtube-video",
      { youtube_url: u, requested_outputs: defaultOutputs },
      orgId,
    );
    setIntakeBusy(false);
    if (!r.ok) {
      setIntakeErr(r.error);
      return;
    }
    setIntakeMsg(`Job ${r.data.job_id} queued (queue ${r.data.queue_id}).`);
    setYtVideoUrl("");
    void refreshCore();
    void loadJobDetail(r.data.job_id);
  };

  const submitYoutubePlaylist = async () => {
    setIntakeBusy(true);
    setIntakeErr(null);
    setIntakeMsg(null);
    const u = ytPlaylistUrl.trim();
    if (!u) {
      setIntakeBusy(false);
      setIntakeErr({ code: "bad_request", status: 400, message: "Paste a youtube.com playlist URL (list=…)." });
      return;
    }
    const r = await browserPost<IntakeYoutubePlaylistResponse>(
      "/v1/intake/youtube-playlist",
      { playlist_url: u },
      orgId,
    );
    setIntakeBusy(false);
    if (!r.ok) {
      setIntakeErr(r.error);
      return;
    }
    setIntakeMsg(`Playlist parent recorded: ${r.data.queue_id} (${r.data.status}).`);
    setYtPlaylistUrl("");
    void refreshCore();
  };

  const runUploadIntake = async () => {
    setUploadBusy(true);
    setUploadErr(null);
    setUploadMsg(null);
    if (!file) {
      setUploadBusy(false);
      setUploadErr({ code: "bad_request", status: 400, message: "Choose a file." });
      return;
    }
    const pr = await browserPost<PresignUploadResponse>(
      "/v1/uploads/presign",
      {
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        file_size_bytes: file.size,
        media_type: "video",
      },
      orgId,
    );
    if (!pr.ok) {
      setUploadBusy(false);
      setUploadErr(pr.error);
      return;
    }
    try {
      const put = await fetch(pr.data.upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file,
      });
      if (!put.ok) {
        setUploadBusy(false);
        setUploadErr({ code: "upstream_error", status: put.status, message: `Upload HTTP ${put.status}` });
        return;
      }
    } catch (e) {
      setUploadBusy(false);
      setUploadErr({ code: "upstream_error", status: 0, message: (e as Error).message });
      return;
    }
    const comp = await browserPost<CompleteUploadResponse>(
      "/v1/uploads/complete",
      { media_asset_id: pr.data.media_asset_id },
      orgId,
    );
    if (!comp.ok) {
      setUploadBusy(false);
      setUploadErr(comp.error);
      return;
    }
    const jr = await browserPost<CreateJobResponse>(
      "/v1/intake/upload",
      { media_asset_id: pr.data.media_asset_id, requested_outputs: defaultOutputs },
      orgId,
    );
    setUploadBusy(false);
    if (!jr.ok) {
      setUploadErr(jr.error);
      return;
    }
    setUploadMsg(`Job ${jr.data.job_id} created.`);
    setFile(null);
    void refreshCore();
    void loadJobDetail(jr.data.job_id);
  };

  const authErr =
    creditsErr?.code === "unauthorized"
      ? creditsErr
      : hintsErr?.code === "unauthorized"
        ? hintsErr
        : orgQueueErr?.code === "unauthorized"
          ? orgQueueErr
          : recentJobsErr?.code === "unauthorized"
            ? recentJobsErr
            : intakeErr?.code === "unauthorized"
              ? intakeErr
              : uploadErr?.code === "unauthorized"
                ? uploadErr
                : detailErr?.code === "unauthorized"
                  ? detailErr
                  : null;

  const selectedYoutubeRow = findYoutubeRow(orgQueue?.items, selectedJobId);
  const selectedJobSummary = findJobSummary(recentJobs?.jobs, selectedJobId);
  const focusOutputs = jobOutputs?.outputs?.filter((o) => YOUTUBE_FOCUS_OUTPUTS.includes(o.type)) ?? [];
  const previewByType = new Map(jsonPreviews.map((p) => [p.title, p.data]));
  const youtubeAcquisitionFailed = Boolean(
    selectedJobSummary?.source_kind === "youtube" &&
      (selectedJobSummary?.acquisition_error || selectedJobSummary?.acquisition_status?.includes("blocked")),
  );
  const failureReason = youtubeAcquisitionFailed
    ? "YouTube acquisition failed. This can happen when YouTube blocks server-side fetches. Try another public URL or upload the file directly."
    : (jobDetail?.failure_message ??
      jobDetail?.failure_reason ??
      jobDetail?.failure_code ??
      selectedYoutubeRow?.acquisition_error ??
      selectedJobSummary?.acquisition_error ??
      null);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-50">Launch portal</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-400">
            Credits, gated YouTube intake, direct upload → job, job list, and JSON previews (summary / products /
            CTAs / FAQs / schema / manifest / downloads). Calls use the Next.js BFF.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refreshCore()}
          className="rounded-lg border border-surface-border bg-surface-raised px-4 py-2 text-sm text-zinc-200"
        >
          Refresh
        </button>
      </div>

      {authErr ? (
        <div role="alert" className="rounded-lg border border-danger/50 bg-danger/10 px-4 py-3 text-sm text-red-100">
          <p className="font-semibold">Auth / proxy</p>
          <p className="mt-1">{authErr.message}</p>
        </div>
      ) : null}

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
        <h2 className="text-lg font-semibold text-zinc-100">Processing allowance</h2>
        {creditsErr && creditsErr.code !== "unauthorized" ? (
          <p className="mt-2 text-sm text-red-300">{creditsErr.message}</p>
        ) : null}
        {credits ? (
          <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <div>
              <dt className="text-zinc-500">Available minutes</dt>
              <dd className="font-mono text-zinc-100">{credits.processing_minutes_available}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Reserved</dt>
              <dd className="font-mono text-zinc-100">{credits.processing_minutes_reserved}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Archive access</dt>
              <dd className="text-zinc-200">{credits.annual_archive_access_status}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Hosting until</dt>
              <dd className="text-zinc-300">{credits.hosting_until ?? "—"}</dd>
            </div>
          </dl>
        ) : (
          <p className="mt-2 text-sm text-zinc-500">No credits payload yet.</p>
        )}
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
        <h2 className="text-lg font-semibold text-zinc-100">Feature flags (worker hints)</h2>
        {hintsErr && hintsErr.code !== "unauthorized" ? (
          <p className="mt-2 text-sm text-red-300">{hintsErr.message}</p>
        ) : null}
        {hints ? (
          <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(hints).map(([k, v]) => (
              <div key={k} className="rounded border border-surface-border/60 px-2 py-1">
                <dt className="text-zinc-500">{k}</dt>
                <dd className="font-mono text-zinc-200">{typeof v === "string" ? v : JSON.stringify(v)}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-surface-border bg-surface-raised/30 p-5 space-y-4">
          <h2 className="text-lg font-semibold text-zinc-100">YouTube video → job</h2>
          <p className="text-xs text-zinc-500">
            Requires API <code className="text-zinc-400">FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED</code>. Stub pipeline
            runs without a downloaded file.
          </p>
          <input
            value={ytVideoUrl}
            onChange={(e) => setYtVideoUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=…"
            className="w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-zinc-100"
          />
          <button
            type="button"
            disabled={intakeBusy}
            onClick={() => void submitYoutubeVideo()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface disabled:opacity-50"
          >
            {intakeBusy ? "Submitting…" : "Create job from video URL"}
          </button>
        </div>
        <div className="rounded-xl border border-surface-border bg-surface-raised/30 p-5 space-y-4">
          <h2 className="text-lg font-semibold text-zinc-100">YouTube playlist (parent)</h2>
          <p className="text-xs text-zinc-500">Creates a parent queue row — expansion not wired in worker yet.</p>
          <input
            value={ytPlaylistUrl}
            onChange={(e) => setYtPlaylistUrl(e.target.value)}
            placeholder="https://www.youtube.com/playlist?list=…"
            className="w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-zinc-100"
          />
          <button
            type="button"
            disabled={intakeBusy}
            onClick={() => void submitYoutubePlaylist()}
            className="rounded-lg border border-surface-border px-4 py-2 text-sm text-zinc-200 disabled:opacity-50"
          >
            Record playlist parent
          </button>
        </div>
      </section>

      {intakeErr && intakeErr.code !== "unauthorized" ? (
        <p className="text-sm text-red-300">{intakeErr.message}</p>
      ) : null}
      {intakeMsg ? <p className="text-sm text-accent">{intakeMsg}</p> : null}

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5 space-y-4">
        <h2 className="text-lg font-semibold text-zinc-100">Direct upload → job</h2>
        <p className="text-xs text-zinc-500">Outputs: {OUTPUT_OPTIONS.map((o) => o.id).join(", ")}</p>
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm text-zinc-300" />
        <button
          type="button"
          disabled={uploadBusy}
          onClick={() => void runUploadIntake()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface disabled:opacity-50"
        >
          {uploadBusy ? "Uploading…" : "Upload & queue job"}
        </button>
        {uploadErr && uploadErr.code !== "unauthorized" ? (
          <p className="text-sm text-red-300">{uploadErr.message}</p>
        ) : null}
        {uploadMsg ? <p className="text-sm text-accent">{uploadMsg}</p> : null}
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
        <h2 className="text-lg font-semibold text-zinc-100">Org YouTube queue</h2>
        {orgQueueErr && orgQueueErr.code !== "unauthorized" ? (
          <p className="mt-2 text-sm text-red-300">{orgQueueErr.message}</p>
        ) : null}
        {orgQueue?.items?.length ? (
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-xs text-zinc-500">
                <th className="py-2">Source</th>
                <th className="py-2">Duration</th>
                <th className="py-2">Status</th>
                <th className="py-2">Acquisition</th>
                <th className="py-2">Failure / URL</th>
              </tr>
            </thead>
            <tbody>
              {orgQueue.items.map((row) => (
                <tr key={row.id} className="border-b border-surface-border/50 align-top">
                  <td className="max-w-[240px] py-2 text-xs">
                    <p className="truncate text-zinc-200">{row.source_title ?? "Untitled YouTube source"}</p>
                    <p className="mt-1 font-mono text-[11px] text-zinc-600">{row.queue_kind ?? "video"}</p>
                  </td>
                  <td className="py-2 font-mono text-xs text-zinc-300">{formatDuration(row.source_duration_seconds)}</td>
                  <td className="py-2 font-mono text-xs">{row.status}</td>
                  <td className="py-2 text-xs">{row.acquisition_status ?? "—"}</td>
                  <td className="max-w-[320px] py-2 text-xs text-zinc-400">
                    {row.acquisition_error ? <p className="mb-1 text-red-300">{row.acquisition_error}</p> : null}
                    <a href={row.youtube_url} className="block truncate text-accent" target="_blank" rel="noreferrer">
                      {row.youtube_url}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="mt-2 text-sm text-zinc-500">No queue rows.</p>
        )}
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-zinc-100">Jobs</h2>
          <Link href="/jobs" className="text-sm text-accent hover:underline">
            Processing page →
          </Link>
        </div>
        {recentJobsErr && recentJobsErr.code !== "unauthorized" ? (
          <p className="mt-2 text-sm text-red-300">{recentJobsErr.message}</p>
        ) : null}
        {recentJobs?.jobs?.length ? (
          <ul className="mt-3 space-y-1 text-sm">
            {recentJobs.jobs.map((j) => (
              <li key={j.job_id} className="rounded border border-surface-border/50 bg-surface/30 p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <button
                      type="button"
                      className={`font-mono text-xs ${selectedJobId === j.job_id ? "text-accent" : "text-zinc-300"}`}
                      onClick={() => void loadJobDetail(j.job_id)}
                    >
                      {j.job_id}
                    </button>
                    <p className="mt-1 text-xs text-zinc-500">
                      {j.source_kind ?? "upload"} · {j.status} · {j.current_stage ?? "—"}
                    </p>
                    {j.source_title ? <p className="mt-1 truncate text-xs text-zinc-300">{j.source_title}</p> : null}
                    {j.acquisition_error ? <p className="mt-1 text-xs text-red-300">{j.acquisition_error}</p> : null}
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-right text-[11px] text-zinc-500 sm:grid-cols-6">
                    <span>Duration {formatDuration(j.source_duration_seconds)}</span>
                    <span>Acq {j.acquisition_status ?? "—"}</span>
                    <span className={j.has_transcript ? "text-accent" : "text-zinc-600"}>Transcript {j.has_transcript ? "yes" : "no"}</span>
                    <span className={j.has_agent_bundle ? "text-accent" : "text-zinc-600"}>Agent {j.has_agent_bundle ? "yes" : "no"}</span>
                    <span className={j.has_hosted_manifest ? "text-accent" : "text-zinc-600"}>Manifest {j.has_hosted_manifest ? "yes" : "no"}</span>
                    <span className={j.has_export_bundle ? "text-accent" : "text-zinc-600"}>Export {j.has_export_bundle ? "yes" : "no"}</span>
                    <span className={j.has_visual_evidence ? "text-accent" : "text-zinc-600"}>Visual {j.has_visual_evidence ? "yes" : "no"}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-zinc-500">No jobs.</p>
        )}
      </section>

      {selectedJobId ? (
        <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">YouTube job outputs — {selectedJobId}</h2>
              <p className="mt-1 text-xs text-zinc-500">
                Completed source context, acquisition state, and the key deliverables Base44 should surface.
              </p>
            </div>
            {jobDetail ? <span className="rounded-full border border-surface-border px-3 py-1 text-xs text-zinc-300">{jobDetail.status}</span> : null}
          </div>
          {detailErr && detailErr.code !== "unauthorized" ? (
            <p className="text-sm text-red-300">{detailErr.message}</p>
          ) : null}

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-surface-border/60 bg-surface/40 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Source</p>
              <p className="mt-2 text-sm font-medium text-zinc-100">{selectedYoutubeRow?.source_title ?? selectedJobSummary?.source_title ?? "—"}</p>
              <p className="mt-1 font-mono text-xs text-zinc-400">
                {selectedJobSummary?.source_kind ?? "upload"} · Duration: {formatDuration(selectedYoutubeRow?.source_duration_seconds ?? selectedJobSummary?.source_duration_seconds)}
              </p>
            </div>
            <div className="rounded-lg border border-surface-border/60 bg-surface/40 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Status / stage</p>
              <p className="mt-2 font-mono text-sm text-zinc-100">{jobDetail?.status ?? selectedJobSummary?.status ?? "—"}</p>
              <p className="mt-1 text-xs text-zinc-500">{jobDetail?.current_stage ?? selectedJobSummary?.current_stage ?? "—"}</p>
            </div>
            <div className="rounded-lg border border-surface-border/60 bg-surface/40 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Acquisition status</p>
              <p className="mt-2 font-mono text-sm text-zinc-100">{selectedYoutubeRow?.acquisition_status ?? selectedJobSummary?.acquisition_status ?? "—"}</p>
              <p className="mt-1 text-xs text-zinc-500">Queue: {selectedYoutubeRow?.status ?? "—"}</p>
            </div>
          </div>

          <div className="grid gap-2 text-xs sm:grid-cols-5">
            <div className={outputExists(jobOutputs, ["raw_transcript", "clean_transcript"]) || selectedJobSummary?.has_transcript ? "rounded border border-accent/30 bg-accent/10 p-2 text-accent" : "rounded border border-surface-border/60 p-2 text-zinc-500"}>
              Transcript {outputExists(jobOutputs, ["raw_transcript", "clean_transcript"]) || selectedJobSummary?.has_transcript ? "exists" : "missing"}
            </div>
            <div className={outputExists(jobOutputs, ["agent_bundle"]) || selectedJobSummary?.has_agent_bundle ? "rounded border border-accent/30 bg-accent/10 p-2 text-accent" : "rounded border border-surface-border/60 p-2 text-zinc-500"}>
              Agent bundle {outputExists(jobOutputs, ["agent_bundle"]) || selectedJobSummary?.has_agent_bundle ? "exists" : "missing"}
            </div>
            <div className={outputExists(jobOutputs, ["hosted_manifest"]) || selectedJobSummary?.has_hosted_manifest ? "rounded border border-accent/30 bg-accent/10 p-2 text-accent" : "rounded border border-surface-border/60 p-2 text-zinc-500"}>
              Hosted manifest {outputExists(jobOutputs, ["hosted_manifest"]) || selectedJobSummary?.has_hosted_manifest ? "exists" : "missing"}
            </div>
            <div className={outputExists(jobOutputs, ["export_bundle"]) || selectedJobSummary?.has_export_bundle ? "rounded border border-accent/30 bg-accent/10 p-2 text-accent" : "rounded border border-surface-border/60 p-2 text-zinc-500"}>
              Export bundle {outputExists(jobOutputs, ["export_bundle"]) || selectedJobSummary?.has_export_bundle ? "exists" : "missing"}
            </div>
            <div className={outputExists(jobOutputs, ["visual_evidence"]) || selectedJobSummary?.has_visual_evidence ? "rounded border border-accent/30 bg-accent/10 p-2 text-accent" : "rounded border border-surface-border/60 p-2 text-zinc-500"}>
              Visual evidence {outputExists(jobOutputs, ["visual_evidence"]) || selectedJobSummary?.has_visual_evidence ? "exists" : "missing"}
            </div>
          </div>

          {failureReason ? (
            <div role="alert" className="rounded-lg border border-danger/50 bg-danger/10 p-3 text-sm text-red-100">
              <p className="font-semibold">Failure reason</p>
              <p className="mt-1">{failureReason}</p>
            </div>
          ) : null}

          {focusOutputs.length ? (
            <div className="grid gap-3 lg:grid-cols-2">
              {focusOutputs.map((o) => (
                <article key={o.type} className="rounded-lg border border-surface-border/60 bg-surface/40 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-zinc-100">{outputLabel(o.type)}</h3>
                      <p className="mt-1 font-mono text-xs text-zinc-500">{o.type} · {o.format}</p>
                    </div>
                    <a href={o.download_url} className="shrink-0 text-xs font-medium text-accent hover:underline" target="_blank" rel="noreferrer">
                      Open
                    </a>
                  </div>
                  {previewByType.has(o.type) ? (
                    <pre className="mt-3 max-h-72 overflow-auto rounded bg-black/40 p-3 text-xs text-zinc-300">
                      {stringifyPreview(previewByType.get(o.type))}
                    </pre>
                  ) : (
                    <p className="mt-3 text-xs text-zinc-500">Preview not fetched; open the signed URL.</p>
                  )}
                </article>
              ))}
            </div>
          ) : jobOutputs ? (
            <p className="rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-amber-100">
              No transcript, media inspection, visual evidence, agent bundle, hosted manifest, or export bundle outputs are ready for this job yet.
            </p>
          ) : null}

          {jobOutputs?.outputs?.length ? (
            <details className="rounded border border-surface-border/60 p-3">
              <summary className="cursor-pointer text-sm text-zinc-200">All downloads ({jobOutputs.outputs.length})</summary>
              <ul className="mt-2 space-y-1 text-sm">
                {jobOutputs.outputs.map((o) => (
                  <li key={o.type}>
                    <a href={o.download_url} className="text-accent hover:underline" target="_blank" rel="noreferrer">
                      {o.title}
                    </a>{" "}
                    <span className="text-zinc-600">({o.type})</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
          {jobDetail ? (
            <details className="rounded border border-surface-border/60 p-3">
              <summary className="cursor-pointer text-sm text-zinc-200">Raw job status payload</summary>
              <pre className="mt-2 overflow-x-auto rounded bg-black/40 p-3 text-xs text-zinc-300">
                {JSON.stringify(jobDetail, null, 2)}
              </pre>
            </details>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
