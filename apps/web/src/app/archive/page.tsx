"use client";

import { useState } from "react";
import type { ManifestResponse } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";

export default function ArchivePage() {
  const [creator, setCreator] = useState("demo-creator");
  const [asset, setAsset] = useState("episode-001");
  const [data, setData] = useState<ManifestResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    setErr(null);
    setData(null);
    const base = process.env.NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL?.replace(/\/$/, "");
    if (!base) {
      setErr("NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL is not set.");
      return;
    }
    const slug = asset.replace(/\.json$/i, "");
    const url = `${base}/v1/manifests/${encodeURIComponent(creator)}/${encodeURIComponent(slug)}.json`;
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    if (!res.ok) {
      setErr(res.status === 404 ? "Not published yet." : `HTTP ${res.status}`);
      setData(null);
      return;
    }
    try {
      setData(JSON.parse(text) as ManifestResponse);
    } catch {
      setErr("Invalid JSON");
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-zinc-50">Archive</h1>
      <p className="max-w-2xl text-sm text-zinc-400">
        Public hosted manifest JSON — fetched directly from the API (no internal key). Use creator and asset slugs.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label htmlFor="creator" className="text-sm font-medium text-zinc-300">
            Creator slug
          </label>
          <input
            id="creator"
            value={creator}
            onChange={(e) => setCreator(e.target.value)}
            className="mt-1 w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-zinc-100"
          />
        </div>
        <div>
          <label htmlFor="asset" className="text-sm font-medium text-zinc-300">
            Asset slug
          </label>
          <input
            id="asset"
            value={asset}
            onChange={(e) => setAsset(e.target.value)}
            className="mt-1 w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-zinc-100"
            placeholder="episode-001"
          />
        </div>
      </div>
      <button
        type="button"
        onClick={() => void load()}
        className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface hover:bg-accent/90"
      >
        Load manifest
      </button>
      {err ? (
        <p role="alert" className="rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-amber-100">
          {err}
        </p>
      ) : null}
      {data && !err ? (
        <div className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
          <h2 className="text-sm font-medium text-zinc-400">Summary</h2>
          <p className="mt-1 text-lg text-zinc-100">
            {(data.canonical_title as string) || (data.summary as string)?.slice?.(0, 120) || "Manifest loaded"}
          </p>
        </div>
      ) : null}
      <DebugPanel title="Manifest JSON" json={data} />
    </div>
  );
}
