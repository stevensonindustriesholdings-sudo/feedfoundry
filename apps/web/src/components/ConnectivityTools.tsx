"use client";

import { useState } from "react";
import { browserGet, browserPost } from "@/lib/client/api";
import { getOrgId } from "@/lib/org-storage";
import type { AccountCreditsResponse, HealthResponse, PresignUploadResponse, ReadyResponse } from "@/lib/types";

type StepLog = { name: string; ok: boolean; detail: string };

/**
 * Optional connectivity checks for operators — lives on System only, not part of core product UX.
 */
export function ConnectivityTools() {
  const [logs, setLogs] = useState<StepLog[]>([]);
  const [busy, setBusy] = useState(false);

  const pushLog = (name: string, ok: boolean, detail: string) => {
    setLogs((prev) => [...prev, { name, ok, detail }]);
  };

  const runHealth = async () => {
    setBusy(true);
    const r = await browserGet<HealthResponse>("/health", null);
    if (r.ok) pushLog("API liveness", true, r.data.status);
    else pushLog("API liveness", false, r.error.message);
    setBusy(false);
  };

  const runReady = async () => {
    setBusy(true);
    const r = await browserGet<ReadyResponse>("/ready", null);
    if (r.ok) pushLog("Readiness", true, r.data.ready ? "all checks passed" : "degraded");
    else pushLog("Readiness", false, r.error.message);
    setBusy(false);
  };

  const runCredits = async () => {
    setBusy(true);
    const r = await browserGet<AccountCreditsResponse>("/v1/account/credits", getOrgId());
    if (r.ok) pushLog("Account credits", true, `${r.data.credits_available} available`);
    else pushLog("Account credits", false, r.error.message);
    setBusy(false);
  };

  const runPresignDry = async () => {
    setBusy(true);
    const r = await browserPost<PresignUploadResponse>(
      "/v1/uploads/presign",
      {
        filename: "connectivity-check.bin",
        content_type: "application/octet-stream",
        file_size_bytes: 1024,
        media_type: "video",
      },
      getOrgId(),
    );
    if (r.ok) pushLog("Presign path", true, "signed URL issued");
    else pushLog("Presign path", false, r.error.message);
    setBusy(false);
  };

  return (
    <section className="rounded-xl border border-zinc-700/50 bg-zinc-950/40 p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">Connectivity</h2>
      <p className="mt-1 text-xs text-zinc-500">
        Quick checks for your team. Full upload and jobs live under Upload and Jobs.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void runHealth()}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
        >
          Liveness
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runReady()}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
        >
          Readiness
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runCredits()}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
        >
          Credits
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runPresignDry()}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
        >
          Presign path
        </button>
        <button
          type="button"
          onClick={() => setLogs([])}
          className="rounded-md border border-dashed border-zinc-700 px-3 py-1.5 text-xs text-zinc-500 hover:bg-zinc-900"
        >
          Clear
        </button>
      </div>
      {logs.length ? (
        <ol className="mt-4 space-y-1 font-mono text-xs text-zinc-400">
          {logs.map((l, i) => (
            <li key={i} className={l.ok ? "text-emerald-400/90" : "text-red-400/90"}>
              {l.ok ? "✓" : "✗"} {l.name}: {l.detail}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
