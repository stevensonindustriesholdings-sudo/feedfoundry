"use client";

import { useMemo, useState } from "react";
import type { ManifestResponse } from "@/lib/types";

function pickString(obj: Record<string, unknown>, keys: string[]): string | undefined {
  for (const k of keys) {
    const v = obj[k];
    if (typeof v === "string" && v.trim()) return v;
  }
  return undefined;
}

export default function ArchivePage() {
  const [creator, setCreator] = useState("demo-creator");
  const [asset, setAsset] = useState("episode-001");
  const [data, setData] = useState<ManifestResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const summary = useMemo(() => {
    if (!data || typeof data !== "object") return null;
    const title =
      pickString(data, ["canonical_title", "title", "episode_title"]) ||
      (typeof data.summary === "string" ? data.summary.slice(0, 140) : undefined);
    const slug = pickString(data, ["slug", "asset_slug", "id"]);
    const published = pickString(data, ["published_at", "updated_at", "created_at"]);
    return { title: title || "Manifest loaded", slug, published };
  }, [data]);

  const load = async () => {
    setErr(null);
    setData(null);
    const base = process.env.NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL?.replace(/\/$/, "");
    if (!base) {
      setErr("Set NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL to load public manifests.");
      return;
    }
    const slug = asset.replace(/\.json$/i, "");
    const url = `${base}/v1/manifests/${encodeURIComponent(creator)}/${encodeURIComponent(slug)}.json`;
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    if (!res.ok) {
      setErr(res.status === 404 ? "Not published yet for this slug." : `Request failed (${res.status}).`);
      setData(null);
      return;
    }
    try {
      setData(JSON.parse(text) as ManifestResponse);
    } catch {
      setErr("Response was not valid JSON.");
    }
  };

  return (
    <div className="space-y-10">
      <header className="max-w-2xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Public</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">Creator archive</h1>
        <p className="text-sm leading-relaxed text-zinc-500">
          Hosted manifest JSON for your <strong className="font-medium text-zinc-400">annual hosted archive</strong>.
          Fetched from the public API URL (no org secret in the browser).
        </p>
      </header>

      <div className="grid gap-5 rounded-2xl border border-surface-border bg-surface-raised/35 p-6 md:grid-cols-2 md:p-7">
        <div>
          <label htmlFor="creator" className="text-sm font-medium text-zinc-300">
            Creator slug
          </label>
          <input
            id="creator"
            value={creator}
            onChange={(e) => setCreator(e.target.value)}
            className="mt-2 w-full rounded-xl border border-surface-border bg-surface px-3 py-2.5 text-sm text-zinc-100"
          />
        </div>
        <div>
          <label htmlFor="asset" className="text-sm font-medium text-zinc-300">
            Episode / asset slug
          </label>
          <input
            id="asset"
            value={asset}
            onChange={(e) => setAsset(e.target.value)}
            className="mt-2 w-full rounded-xl border border-surface-border bg-surface px-3 py-2.5 text-sm text-zinc-100"
            placeholder="episode-001"
          />
        </div>
      </div>

      <button
        type="button"
        onClick={() => void load()}
        className="rounded-xl bg-accent px-6 py-2.5 text-sm font-semibold text-surface hover:bg-accent/90"
      >
        Load manifest
      </button>

      {err ? (
        <p role="alert" className="rounded-2xl border border-warn/30 bg-warn/10 px-5 py-4 text-sm text-amber-100">
          {err}
        </p>
      ) : null}

      {data && !err && summary ? (
        <article className="rounded-2xl border border-surface-border bg-surface-raised/50 p-6 md:p-8">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Episode</h2>
          <p className="mt-2 text-xl font-semibold leading-snug text-zinc-50">{summary.title}</p>
          <dl className="mt-6 grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-zinc-500">Creator</dt>
              <dd className="mt-1 font-mono text-zinc-200">{creator}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Asset</dt>
              <dd className="mt-1 font-mono text-zinc-200">{asset.replace(/\.json$/i, "")}</dd>
            </div>
            {summary.slug ? (
              <div>
                <dt className="text-zinc-500">Manifest id</dt>
                <dd className="mt-1 font-mono text-zinc-200">{summary.slug}</dd>
              </div>
            ) : null}
            {summary.published ? (
              <div>
                <dt className="text-zinc-500">Timestamp</dt>
                <dd className="mt-1 text-zinc-200">{summary.published}</dd>
              </div>
            ) : null}
          </dl>
        </article>
      ) : null}

      {data && !err ? (
        <details className="rounded-2xl border border-dashed border-surface-border bg-surface/40 p-4 text-sm">
          <summary className="cursor-pointer font-medium text-zinc-500">Manifest JSON (technical)</summary>
          <pre className="mt-3 max-h-[min(70vh,28rem)] overflow-auto rounded-xl bg-black/35 p-4 font-mono text-xs leading-relaxed text-zinc-400">
            {JSON.stringify(data, null, 2)}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
