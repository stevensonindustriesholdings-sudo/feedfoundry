import Link from "next/link";

import {
  STORAGE_VIEWER_CREDENTIALS_MISSING,
  applyQuickFilter,
  isQuickFilter,
  listStorageObjects,
  storageViewerBucketNameForDisplay,
} from "@/lib/server/storage-viewer";

export const dynamic = "force-dynamic";

type PageProps = {
  searchParams: Promise<{ prefix?: string; filter?: string; continuation?: string }>;
};

function buildHref(q: { prefix?: string; filter?: string; continuation?: string }): string {
  const u = new URLSearchParams();
  if (q.prefix !== undefined) u.set("prefix", q.prefix);
  if (q.filter !== undefined && q.filter !== "") u.set("filter", q.filter);
  if (q.continuation !== undefined && q.continuation !== "") u.set("continuation", q.continuation);
  const s = u.toString();
  return s ? `/system/storage?${s}` : "/system/storage";
}

export default async function SystemStoragePage(props: PageProps) {
  const sp = await props.searchParams;
  const rawPrefix = sp.prefix;
  const prefix = rawPrefix === undefined ? "orgs/" : rawPrefix;
  const filterRaw = sp.filter?.trim();
  const filter = isQuickFilter(filterRaw) ? filterRaw : undefined;
  const continuation = sp.continuation?.trim() || undefined;

  const listed = await listStorageObjects({ prefix, continuationToken: continuation });
  const bucketHint = storageViewerBucketNameForDisplay();

  const rows =
    !listed.ok ? [] : filter ? applyQuickFilter(listed.objects, filter) : listed.objects;

  const truncatedNote =
    listed.ok && listed.isTruncated
      ? "This prefix has more objects in storage than shown on this page. Use “Next page” or a narrower prefix."
      : null;

  const nextHref =
    listed.ok && listed.isTruncated && listed.nextContinuationToken
      ? buildHref({
          prefix,
          ...(filter ? { filter } : {}),
          continuation: listed.nextContinuationToken,
        })
      : null;

  return (
    <div className="space-y-8">
      <div className="max-w-3xl space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Operators</p>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-50">Storage viewer</h1>
        <p className="text-sm leading-relaxed text-zinc-500">
          Objects in bucket <span className="font-mono text-zinc-300">{bucketHint}</span> (read on the server only —
          keys are never sent with R2 secrets).
        </p>
        <p className="text-xs text-zinc-600">
          <Link href="/system" className="text-accent no-underline hover:underline">
            ← System
          </Link>
        </p>
      </div>

      <section className="rounded-2xl border border-surface-border bg-surface-raised/35 p-5 md:p-6">
        <h2 className="text-sm font-semibold text-zinc-200">Prefix</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Default is <span className="font-mono text-zinc-400">orgs/</span>. Submit empty to list from the bucket root
          (can be slow on large buckets).
        </p>
        <form method="get" className="mt-4 flex flex-wrap items-end gap-3">
          <label className="block min-w-[12rem] flex-1 text-xs text-zinc-500">
            <span className="mb-1 block font-medium text-zinc-400">Prefix</span>
            <input
              type="text"
              name="prefix"
              defaultValue={prefix}
              className="w-full rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono text-sm text-zinc-100"
              autoComplete="off"
            />
          </label>
          {filter ? <input type="hidden" name="filter" value={filter} /> : null}
          <button
            type="submit"
            className="rounded-lg border border-accent/40 bg-accent/15 px-4 py-2 text-sm font-medium text-accent hover:bg-accent/25"
          >
            List
          </button>
        </form>

        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Quick filters</h3>
          <p className="mt-1 text-xs text-zinc-600">
            Applied to the current result page (same S3 prefix). Narrow the prefix if a filter looks empty.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(
              [
                ["source", "Source files"],
                ["outputs", "Outputs"],
                ["media_inspection", "media_inspection"],
                ["raw_transcript", "raw_transcript"],
                ["hosted_manifest", "hosted_manifest"],
              ] as const
            ).map(([id, label]) => (
              <Link
                key={id}
                href={buildHref({ prefix, filter: id })}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium no-underline ${
                  filter === id
                    ? "border-accent bg-accent/20 text-accent"
                    : "border-surface-border text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
                }`}
              >
                {label}
              </Link>
            ))}
            <Link
              href={buildHref({ prefix })}
              className="rounded-lg border border-dashed border-zinc-600 px-3 py-1.5 text-xs text-zinc-500 no-underline hover:text-zinc-300"
            >
              Clear filter
            </Link>
            <Link
              href={buildHref({ prefix: "orgs/" })}
              className="rounded-lg border border-dashed border-zinc-600 px-3 py-1.5 text-xs text-zinc-500 no-underline hover:text-zinc-300"
            >
              Default prefix (orgs/)
            </Link>
            <Link
              href={buildHref({ prefix: "" })}
              className="rounded-lg border border-dashed border-zinc-600 px-3 py-1.5 text-xs text-zinc-500 no-underline hover:text-zinc-300"
            >
              Whole bucket
            </Link>
          </div>
        </div>
      </section>

      {!listed.ok ? (
        <div
          role="alert"
          className={`rounded-2xl border px-5 py-4 text-sm ${
            listed.message === STORAGE_VIEWER_CREDENTIALS_MISSING
              ? "border-amber-500/40 bg-amber-500/10 text-amber-100"
              : "border-danger/35 bg-danger/10 text-red-100"
          }`}
        >
          {listed.message}
        </div>
      ) : (
        <>
          {truncatedNote ? <p className="text-xs text-amber-200/90">{truncatedNote}</p> : null}
          {filter ? (
            <p className="text-xs text-zinc-500">
              Quick filter: <span className="font-mono text-zinc-400">{filter}</span> — showing {rows.length} of{" "}
              {listed.objects.length} keys on this page.
            </p>
          ) : (
            <p className="text-xs text-zinc-500">
              {rows.length} object{rows.length === 1 ? "" : "s"} on this page.
            </p>
          )}
          <div className="overflow-x-auto rounded-2xl border border-surface-border">
            <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border bg-surface/50 text-xs uppercase tracking-wide text-zinc-500">
                  <th className="px-4 py-3 font-medium">Key</th>
                  <th className="px-4 py-3 font-medium">Size</th>
                  <th className="px-4 py-3 font-medium">Last modified</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-center text-sm text-zinc-500">
                      No objects match this view.
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.key} className="border-b border-surface-border/60 align-top">
                      <td className="px-4 py-2 font-mono text-[11px] text-zinc-300 break-all">{r.key}</td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-zinc-400">
                        {r.size === null ? "—" : formatBytes(r.size)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-zinc-500">
                        {r.lastModified ?? "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {nextHref ? (
            <p className="text-sm">
              <Link href={nextHref} className="font-medium text-accent no-underline hover:underline">
                Next page →
              </Link>
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MiB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GiB`;
}
