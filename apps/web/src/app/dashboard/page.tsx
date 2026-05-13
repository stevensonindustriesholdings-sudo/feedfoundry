"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  browserGetAccountCreditsWithDiagnostics,
  type AccountCreditsLoadDiagnostics,
} from "@/lib/client/api";
import { getOrgId } from "@/lib/org-storage";
import type { AccountCreditsResponse } from "@/lib/types";
import type { ClientError } from "@/lib/errors";
import { DebugPanel } from "@/components/DebugPanel";

const API_ERROR = {
  title: "FeedFoundry API error",
  body: "The backend responded, but returned a server error.",
} as const;

/** Strip common secret patterns from diagnostic strings (response bodies may echo headers). */
function redactDiagnosticsText(s: string, maxLen = 12000): string {
  return s
    .replace(/Bearer\s+[\w-._~+/=]+/gi, "Bearer [redacted]")
    .replace(/("authorization"\s*:\s*")[^"]*(")/gi, "$1[redacted]$2")
    .slice(0, maxLen);
}

function sanitizeDiagnosticsValue(value: unknown): unknown {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map(sanitizeDiagnosticsValue);
  const out: Record<string, unknown> = {};
  const secretKey = /^(authorization|x-ff-internal-key|x-api-key|password|secret|token)$/i;
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (secretKey.test(k)) out[k] = "[redacted]";
    else if (typeof v === "string" && /bearer\s+/i.test(v)) out[k] = redactDiagnosticsText(v, 500);
    else out[k] = sanitizeDiagnosticsValue(v);
  }
  return out;
}

function formatProcessingMinutes(totalMinutes: number): string {
  if (!Number.isFinite(totalMinutes) || totalMinutes < 0) return "—";
  const h = Math.floor(totalMinutes / 60);
  const m = Math.round(totalMinutes % 60);
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} hr`;
  return `${h} hr ${m} min`;
}

/**
 * Dashboard-only copy for account processing time (GET via server proxy). Order matters: entitlement/auth before generic 5xx.
 * "Backend unavailable" only when code is network_unreachable (true fetch / proxy upstream failure).
 */
function creditsErrorPresentation(err: ClientError): { title: string; body: string } {
  const d = (
    typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail ?? "")
  ).toLowerCase();

  if (err.status === 401 || err.code === "unauthorized") {
    return {
      title: "Server-side API key issue",
      body: "The FeedFoundry backend is reachable, but the local web proxy is missing or using an invalid internal API key. Check FEEDFOUNDRY_INTERNAL_API_KEY in apps/web/.env.local and restart npm run dev.",
    };
  }

  if (err.status === 404 && d.includes("annual_access_not_configured")) {
    return {
      title: "Annual archive access not configured",
      body: "The backend is reachable, but this staging organisation does not yet have an active annual archive access row.",
    };
  }

  if (err.status === 404 && d.includes("annual_access_required")) {
    return {
      title: "Annual archive access required",
      body: "This organisation needs annual archive access before uploads or processing jobs can run.",
    };
  }

  if (err.code === "annual_access_required") {
    return {
      title: "Annual archive access required",
      body: "This organisation needs annual archive access before uploads or processing jobs can run.",
    };
  }

  if (err.status === 403 && (d.includes("access_inactive") || d.includes("annual_access"))) {
    return {
      title: "Annual archive access required",
      body: "This organisation needs annual archive access before uploads or processing jobs can run.",
    };
  }

  if (err.code === "forbidden") {
    return {
      title: "Upstream denied the request (403)",
      body: "The API returned 403 for this organisation or route (see diagnostics for detail).",
    };
  }

  if (err.code === "insufficient_credits" || (err.status === 400 && d.includes("insufficient_credits"))) {
    return {
      title: "Not enough processing time",
      body: "This organisation does not have enough processing time for the requested job.",
    };
  }

  if (err.code === "insufficient_processing_time" || (err.status === 400 && d.includes("insufficient_processing_time"))) {
    return {
      title: "Not enough processing time",
      body: "This upload needs more processing minutes than are available. Top up or choose a shorter file.",
    };
  }

  if (err.code === "network_unreachable") {
    return {
      title: "Backend unavailable",
      body: "The app could not reach the FeedFoundry API.",
    };
  }

  if (err.code === "server_misconfigured") {
    return {
      title: "Local server configuration",
      body: "The Next.js server is missing FEEDFOUNDRY_API_BASE_URL or FEEDFOUNDRY_INTERNAL_API_KEY (server-only). Set them in apps/web/.env.local and restart npm run dev.",
    };
  }

  if (err.code === "proxy_handler_error") {
    return {
      title: "Local proxy error",
      body: "The /api/ff route threw while forwarding. Check the terminal running next dev for the stack trace.",
    };
  }

  if (err.code === "upstream_error" || err.status >= 500) {
    return { title: API_ERROR.title, body: API_ERROR.body };
  }

  return {
    title: "Could not load account processing time",
    body: err.message,
  };
}

function alertTone(err: ClientError): "warn" | "danger" | "neutral" {
  if (err.code === "annual_access_not_configured") return "warn";
  if (
    err.code === "unauthorized" ||
    err.code === "upstream_error" ||
    err.code === "network_unreachable" ||
    err.code === "server_misconfigured" ||
    err.code === "proxy_handler_error" ||
    err.code === "forbidden"
  )
    return "danger";
  if (err.code === "annual_access_required" || err.code === "insufficient_processing_time") return "warn";
  return "neutral";
}

export default function DashboardPage() {
  const [data, setData] = useState<AccountCreditsResponse | null>(null);
  const [error, setError] = useState<ClientError | null>(null);
  const [diagnostics, setDiagnostics] = useState<AccountCreditsLoadDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await browserGetAccountCreditsWithDiagnostics(getOrgId());
    setDiagnostics(res.diagnostics);
    if (res.ok) {
      setData(res.data);
    } else {
      setData(null);
      setError(res.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const errPresentation = error ? creditsErrorPresentation(error) : null;
  const tone = error ? alertTone(error) : "neutral";

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Account</p>
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">Dashboard</h1>
          <p className="max-w-xl text-sm text-zinc-500">
            Annual hosted archive status and processing time for the organisation selected in your browser.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-xl border border-surface-border px-4 py-2.5 text-sm font-medium text-zinc-200 hover:bg-surface-raised"
          >
            Refresh
          </button>
          <Link
            href="/upload"
            className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-surface no-underline hover:bg-accent/90"
          >
            New upload
          </Link>
        </div>
      </div>

      <section className="rounded-2xl border border-surface-border bg-surface-raised/35 p-5 md:p-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Workflow</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { href: "/upload", label: "Upload", desc: "Send media and queue a job" },
            { href: "/jobs", label: "Jobs", desc: "Track progress and processing time" },
            { href: "/outputs", label: "Outputs", desc: "Download deliverables" },
            { href: "/archive", label: "Public archive", desc: "Preview hosted manifests" },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="group rounded-xl border border-surface-border/80 bg-surface/40 p-4 no-underline transition hover:border-zinc-600 hover:bg-surface-raised/50"
            >
              <p className="font-medium text-zinc-100 group-hover:text-white">{item.label}</p>
              <p className="mt-1 text-xs text-zinc-500">{item.desc}</p>
            </Link>
          ))}
        </div>
        <p className="mt-4 text-center text-xs text-zinc-600 md:text-left">
          <Link href="/system" className="text-zinc-500 no-underline hover:text-zinc-400">
            Service status, OpenAPI, and connectivity checks →
          </Link>
        </p>
      </section>

      {loading ? <p className="text-sm text-zinc-500">Loading account…</p> : null}

      {error && errPresentation ? (
        <div
          role="alert"
          className={`rounded-2xl border px-5 py-4 text-sm ${
            tone === "warn"
              ? "border-warn/40 bg-warn/10 text-amber-100"
              : tone === "danger"
                ? "border-danger/40 bg-danger/10 text-red-100"
                : "border-surface-border bg-surface-raised/50 text-zinc-200"
          }`}
        >
          <p className="text-base font-semibold text-zinc-50">{errPresentation.title}</p>
          <p className="mt-2 leading-relaxed opacity-95">{errPresentation.body}</p>
          {error.code === "annual_access_not_configured" ? (
            <p className="mt-3 text-amber-100/90">
              <Link href="/pricing" className="font-medium text-amber-50 underline underline-offset-2">
                View pricing
              </Link>
            </p>
          ) : null}
        </div>
      ) : null}

      {data ? (
        <div className="space-y-4">
          {(() => {
            const available =
              data.processing_minutes_available ?? data.credits_available ?? 0;
            const reserved = data.processing_minutes_reserved ?? data.credits_reserved ?? 0;
            const used = data.processing_minutes_used_lifetime ?? data.credits_spent_lifetime ?? 0;
            const periodEnd =
              data.next_processing_period_end ?? data.next_credit_expiry ?? "—";
            return (
              <>
                {reserved > 0 ? (
                  <p className="text-sm text-amber-100/90">
                    Currently processing — {formatProcessingMinutes(available)} processing time remaining (hours /
                    minutes).
                  </p>
                ) : (
                  <p className="text-sm text-zinc-500">
                    Processing time remaining:{" "}
                    <span className="font-medium text-zinc-200">{formatProcessingMinutes(available)}</span>
                  </p>
                )}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <StatCard label="Archive access" value={data.annual_access_status} highlight />
                  <StatCard
                    label="Processing time remaining"
                    value={formatProcessingMinutes(available)}
                    tone="ok"
                  />
                  <StatCard
                    label="Processing time reserved"
                    value={formatProcessingMinutes(reserved)}
                    tone="pending"
                  />
                  <StatCard label="Processing time used (lifetime)" value={formatProcessingMinutes(used)} />
                  <StatCard label="Hosting until" value={data.hosting_until ?? "—"} />
                  <StatCard label="Current period ends" value={periodEnd} />
                  <StatCard
                    label="Goodwill minutes (this year)"
                    value={String(data.goodwill_processing_minutes_granted_ytd ?? 0)}
                  />
                </div>
              </>
            );
          })()}
        </div>
      ) : null}

      {diagnostics ? (
        <DebugPanel
          title="Account processing time (via server proxy)"
          json={{
            orgId: diagnostics.localOrgId,
            effectiveOrgHeader:
              diagnostics.effectiveOrgHeader === null || diagnostics.effectiveOrgHeader === ""
                ? "(none — server uses FEEDFOUNDRY_DEFAULT_ORG_ID)"
                : diagnostics.effectiveOrgHeader,
            proxyRoute: diagnostics.proxyUrl,
            httpStatus: diagnostics.httpStatus,
            mappedErrorCode: diagnostics.mappedCode,
            outcomeSummary: diagnostics.outcomeSummary,
            responseJsonSafe: sanitizeDiagnosticsValue(diagnostics.parsedJson),
            rawResponseBodyRedacted: redactDiagnosticsText(diagnostics.rawBody),
          }}
        />
      ) : null}
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
  highlight,
}: {
  label: string;
  value: string;
  tone?: "ok" | "pending";
  highlight?: boolean;
}) {
  const border = highlight
    ? "border-accent/35 ring-1 ring-accent/15"
    : tone === "ok"
      ? "border-accent/30"
      : tone === "pending"
        ? "border-warn/30"
        : "border-surface-border";
  return (
    <article className={`rounded-2xl border ${border} bg-surface-raised/45 p-5`}>
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">{value}</p>
    </article>
  );
}
