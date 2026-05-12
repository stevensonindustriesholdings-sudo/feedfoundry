"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { browserGet } from "@/lib/client/api";
import { getOrgId } from "@/lib/org-storage";
import type { AccountCreditsResponse } from "@/lib/types";
import { DebugPanel } from "@/components/DebugPanel";
import { SmokePathCard } from "@/components/SmokePathCard";
import type { ClientError } from "@/lib/errors";

function errorMessage(err: ClientError): string {
  return err.message;
}

export default function DashboardPage() {
  const [data, setData] = useState<AccountCreditsResponse | null>(null);
  const [error, setError] = useState<ClientError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await browserGet<AccountCreditsResponse>("/v1/account/credits", getOrgId());
    if (res.ok) setData(res.data);
    else setError(res.error);
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
          <p className="mt-1 text-sm text-zinc-400">Annual archive access and processing credits for your org.</p>
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
            <p className="mt-2 text-red-100/80">Check server env <code className="rounded bg-black/30 px-1">FEEDFOUNDRY_INTERNAL_API_KEY</code> matches Railway.</p>
          ) : null}
        </div>
      ) : null}

      {data ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <StatCard label="Access status" value={data.annual_access_status} />
          <StatCard label="Credits available" value={String(data.credits_available)} tone="ok" />
          <StatCard label="Credits reserved" value={String(data.credits_reserved)} tone="pending" />
          <StatCard label="Credits spent (lifetime)" value={String(data.credits_spent_lifetime)} />
          <StatCard label="Hosting until" value={data.hosting_until ?? "—"} />
          <StatCard label="Next credit expiry" value={data.next_credit_expiry ?? "—"} />
        </div>
      ) : null}

      <SmokePathCard />
      <DebugPanel title="GET /v1/account/credits" json={data ?? error} />
    </div>
  );
}

function StatCard({ label, value, tone }: { label: string; value: string; tone?: "ok" | "pending" }) {
  const border =
    tone === "ok" ? "border-accent/40" : tone === "pending" ? "border-warn/40" : "border-surface-border";
  return (
    <article className={`rounded-xl border ${border} bg-surface-raised/40 p-4`}>
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-zinc-100">{value}</p>
    </article>
  );
}
