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
        "agent_bundle",
        "raw_transcript",
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
                <th className="py-2">Status</th>
                <th className="py-2">Kind</th>
                <th className="py-2">Acquisition</th>
                <th className="py-2">URL</th>
              </tr>
            </thead>
            <tbody>
              {orgQueue.items.map((row) => (
                <tr key={row.id} className="border-b border-surface-border/50">
                  <td className="py-2 font-mono text-xs">{row.status}</td>
                  <td className="py-2 text-xs">{row.queue_kind ?? "—"}</td>
                  <td className="py-2 text-xs">{row.acquisition_status ?? "—"}</td>
                  <td className="max-w-[240px] truncate py-2 text-xs text-zinc-400">
                    <a href={row.youtube_url} className="text-accent" target="_blank" rel="noreferrer">
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
              <li key={j.job_id}>
                <button
                  type="button"
                  className={`font-mono text-xs ${selectedJobId === j.job_id ? "text-accent" : "text-zinc-300"}`}
                  onClick={() => void loadJobDetail(j.job_id)}
                >
                  {j.job_id}
                </button>{" "}
                <span className="text-zinc-500">{j.status}</span>{" "}
                <span className="text-zinc-600">{j.current_stage ?? ""}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-zinc-500">No jobs.</p>
        )}
      </section>

      {selectedJobId ? (
        <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5 space-y-4">
          <h2 className="text-lg font-semibold text-zinc-100">Job detail — {selectedJobId}</h2>
          {detailErr && detailErr.code !== "unauthorized" ? (
            <p className="text-sm text-red-300">{detailErr.message}</p>
          ) : null}
          {jobDetail ? (
            <pre className="overflow-x-auto rounded bg-black/40 p-3 text-xs text-zinc-300">
              {JSON.stringify(jobDetail, null, 2)}
            </pre>
          ) : null}
          {jobOutputs?.outputs?.length ? (
            <div>
              <h3 className="text-sm font-semibold text-zinc-200">Downloads</h3>
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
            </div>
          ) : null}
          {jsonPreviews.map((p) => (
            <details key={p.title} className="rounded border border-surface-border/60 p-2">
              <summary className="cursor-pointer text-sm text-zinc-200">{p.title}.json preview</summary>
              <pre className="mt-2 max-h-64 overflow-auto text-xs text-zinc-400">
                {typeof p.data === "string" ? p.data : JSON.stringify(p.data, null, 2)}
              </pre>
            </details>
          ))}
        </section>
      ) : null}
    </div>
  );
}
