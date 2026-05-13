"use client";

import { useState } from "react";
import { browserGet, browserPost } from "@/lib/client/api";
import { getOrgId } from "@/lib/org-storage";
import type { AccountCreditsResponse, HealthResponse, PresignUploadResponse, ReadyResponse } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";

type StepLog = { name: string; ok: boolean; detail: string };

export function SmokePathCard() {
  const [logs, setLogs] = useState<StepLog[]>([]);
  const [busy, setBusy] = useState(false);
  const [lastPayload, setLastPayload] = useState<unknown>(null);

  const pushLog = (name: string, ok: boolean, detail: string) => {
    setLogs((prev) => [...prev, { name, ok, detail }]);
  };

  const runHealth = async () => {
    setBusy(true);
    const r = await browserGet<HealthResponse>("/health", null);
    if (r.ok) {
      pushLog("GET /health", true, r.data.status);
      setLastPayload(r.data);
    } else pushLog("GET /health", false, r.error.message);
    setBusy(false);
  };

  const runReady = async () => {
    setBusy(true);
    const r = await browserGet<ReadyResponse>("/ready", null);
    if (r.ok) {
      pushLog("GET /ready", true, r.data.ready ? "ready" : "not ready");
      setLastPayload(r.data);
    } else pushLog("GET /ready", false, r.error.message);
    setBusy(false);
  };

  const runCredits = async () => {
    setBusy(true);
    const r = await browserGet<AccountCreditsResponse>("/v1/account/credits", getOrgId());
    if (r.ok) {
      pushLog("GET /v1/account/credits", true, `available_units=${r.data.credits_available} (UI maps to processing time)`);
      setLastPayload(r.data);
    } else pushLog("GET /v1/account/credits", false, r.error.message);
    setBusy(false);
  };

  const runPresignDry = async () => {
    setBusy(true);
    const r = await browserPost<PresignUploadResponse>(
      "/v1/uploads/presign",
      {
        filename: "smoke-check.bin",
        content_type: "application/octet-stream",
        file_size_bytes: 1024,
        media_type: "video",
      },
      getOrgId(),
    );
    if (r.ok) {
      pushLog("POST /v1/uploads/presign", true, r.data.media_asset_id);
      setLastPayload(r.data);
    } else pushLog("POST /v1/uploads/presign", false, r.error.message);
    setBusy(false);
  };

  const runClear = () => {
    setLogs([]);
    setLastPayload(null);
  };

  return (
    <section className="rounded-xl border border-surface-border bg-surface-raised/30 p-5">
      <h2 className="text-lg font-semibold text-zinc-100">Backend smoke checks</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Staging helpers — each step is manual. Full upload and job creation (processing reservation) stay on the Upload
        page.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void runHealth()}
          className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-zinc-200 hover:bg-surface-border/40 disabled:opacity-50"
        >
          /health
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runReady()}
          className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-zinc-200 hover:bg-surface-border/40 disabled:opacity-50"
        >
          /ready
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runCredits()}
          className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-zinc-200 hover:bg-surface-border/40 disabled:opacity-50"
        >
          account / allowance
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runPresignDry()}
          className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-zinc-200 hover:bg-surface-border/40 disabled:opacity-50"
        >
          presign (dry)
        </button>
        <button
          type="button"
          onClick={runClear}
          className="rounded-md border border-dashed border-zinc-600 px-3 py-1.5 text-sm text-zinc-400 hover:bg-surface-border/30"
        >
          Clear log
        </button>
      </div>
      {logs.length ? (
        <ol className="mt-4 space-y-1 text-sm">
          {logs.map((l, i) => (
            <li key={i} className={l.ok ? "text-accent" : "text-danger"}>
              {l.ok ? "✓" : "✗"} {l.name}: {l.detail}
            </li>
          ))}
        </ol>
      ) : null}
      <DebugPanel title="Last smoke response" json={lastPayload} />
    </section>
  );
}
