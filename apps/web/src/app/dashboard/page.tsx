"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { browserGet } from "@/lib/client/api";
import { getOrgId } from "@/lib/org-storage";
import type { AccountProcessingBalanceResponse } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";
import { SmokePathCard } from "@/components/SmokePathCard";
import type { ClientError } from "@/lib/errors";
import { formatApiUnitsAsProcessing } from "@/lib/processing-display";

function errorMessage(err: ClientError): string {
  return err.message;
}

function minutesAvailable(data: AccountProcessingBalanceResponse): number {
  return data.processing_minutes_available ?? data.credits_available ?? 0;
}

function minutesReserved(data: AccountProcessingBalanceResponse): number {
  return data.processing_minutes_reserved ?? data.credits_reserved ?? 0;
}

function minutesUsedLifetime(data: AccountProcessingBalanceResponse): number {
  return data.processing_minutes_used_lifetime ?? data.credits_spent_lifetime ?? 0;
}

function periodEndLabel(data: AccountProcessingBalanceResponse): string {
  return data.processing_period_ends_on ?? data.next_credit_expiry ?? "—";
}

export default function DashboardPage() {
  const [data, setData] = useState<AccountProcessingBalanceResponse | null>(null);
  const [usageMirror, setUsageMirror] = useState<AccountProcessingBalanceResponse | null>(null);
  const [error, setError] = useState<ClientError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await browserGet<AccountProcessingBalanceResponse>("/v1/account", getOrgId());
    if (!res.ok) {
      setError(res.error);
      setData(null);
      setUsageMirror(null);
      setLoading(false);
      return;
    }
    setData(res.data);
    const usage = await browserGet<AccountProcessingBalanceResponse>("/v1/account/usage", getOrgId());
    setUsageMirror(usage.ok ? usage.data : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-zinc-50">Dashboard</h1>
          <p className="mt-1 max-w-xl text-sm text-zinc-400">
            Annual hosted archive access and remaining processing time for your organisation. Balances load from{" "}
            <span className="font-mono text-zinc-500">GET /v1/account</span> (mirrored by{" "}
            <span className="font-mono text-zinc-500">GET /v1/account/usage</span>).
          </p>
        </div>
        <Link
          href="/upload"
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface no-underline hover:bg-accent/90"
        >
          Upload media
        </Link>
      </div>

      {loading ? <p className="text-zinc-400">Loading account…</p> : null}

      {error ? (
        <div
          role="alert"
          className={`rounded-lg border px-4 py-3 text-sm ${
            error.code === "annual_access_not_configured"
              ? "border-warn/50 bg-warn/10 text-amber-100"
              : "border-danger/50 bg-danger/10 text-red-100"
          }`}
        >
          <p className="font-medium">{errorMessage(error)}</p>
          {error.code === "annual_access_not_configured" ? (
            <p className="mt-2 text-amber-100/80">
              Annual archive access is not active for this organisation.{" "}
              <Link href="/pricing" className="text-amber-50 underline">
                View pricing
              </Link>
            </p>
          ) : null}
          {error.code === "unauthorized" ? (
            <p className="mt-2 text-red-100/80">
              Check server env <code className="rounded bg-black/30 px-1">FEEDFOUNDRY_INTERNAL_API_KEY</code> matches
              Railway.
            </p>
          ) : null}
        </div>
      ) : null}

      {data ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <StatCard label="Archive access" value={data.annual_archive_access_status} />
            <StatCard
              label="Processing time available"
              value={formatApiUnitsAsProcessing(minutesAvailable(data))}
              tone="ok"
            />
            <StatCard
              label="Held for active jobs"
              value={formatApiUnitsAsProcessing(minutesReserved(data))}
              tone="pending"
            />
            <StatCard label="Lifetime processing used" value={formatApiUnitsAsProcessing(minutesUsedLifetime(data))} />
            <StatCard label="Hosting until" value={data.hosting_until ?? "—"} />
            <StatCard label="Processing period ends" value={periodEndLabel(data)} />
            <StatCard
              label="Approx. hours available (API)"
              value={typeof data.processing_hours_available === "number" ? `${data.processing_hours_available} hr` : "—"}
            />
          </div>
        </>
      ) : null}

      <SmokePathCard />
      <DebugPanel
        title="GET /v1/account + GET /v1/account/usage"
        json={{
          account: data ?? null,
          usageMirror: usageMirror ?? null,
          usageMatches:
            data && usageMirror
              ? minutesAvailable(data) === minutesAvailable(usageMirror) &&
                minutesReserved(data) === minutesReserved(usageMirror)
              : null,
          error: error ?? null,
        }}
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "pending";
}) {
  const border =
    tone === "ok" ? "border-accent/40" : tone === "pending" ? "border-warn/40" : "border-surface-border";
  return (
    <article className={`rounded-xl border ${border} bg-surface-raised/40 p-4`}>
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-zinc-100">{value}</p>
    </article>
  );
}
