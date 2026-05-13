import type { ClientError, ClientErrorCode } from "./errors";
import { mapUpstreamError } from "./errors";
import type { AccountCreditsResponse } from "@/lib/types";

const API_PREFIX = "/api/ff";

function orgHeaders(orgId: string | null): HeadersInit {
  const h: Record<string, string> = {};
  if (orgId) h["x-feedfoundry-org-id"] = orgId;
  return h;
}

/** Normalize FastAPI `detail` (string, validation array, or other JSON) for error mapping. */
export function extractFastApiDetail(bodyText: string): string | undefined {
  try {
    const j = JSON.parse(bodyText) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && !Array.isArray(d)) {
      const o = d as Record<string, unknown>;
      if (o.error === "INSUFFICIENT_PROCESSING_TIME") {
        const msg = typeof o.message === "string" ? o.message : "";
        return `insufficient_processing_time ${msg}`.trim();
      }
      if (typeof o.message === "string") return o.message;
      return JSON.stringify(d);
    }
    if (Array.isArray(d) && d.length > 0) {
      const first = d[0] as Record<string, unknown>;
      if (first && typeof first.msg === "string") return String(first.msg);
      return JSON.stringify(d);
    }
  } catch {
    /* not JSON */
  }
  try {
    const j = JSON.parse(bodyText) as { error?: unknown; message?: unknown };
    const e = typeof j.error === "string" ? j.error : "";
    const m = typeof j.message === "string" ? j.message : "";
    if (e && m) return `${e} ${m}`;
    if (m) return m;
    if (e) return e;
  } catch {
    /* ignore */
  }
  return undefined;
}

async function parseJson<T>(res: Response): Promise<{ ok: true; data: T } | { ok: false; error: ClientError }> {
  const text = await res.text();
  const detail = extractFastApiDetail(text);
  if (!res.ok) {
    return { ok: false, error: mapUpstreamError(res.status, detail) };
  }
  try {
    return { ok: true, data: JSON.parse(text) as T };
  } catch {
    return {
      ok: false,
      error: { code: "upstream_error", status: res.status, message: "Invalid JSON from API", detail },
    };
  }
}

export type AccountCreditsLoadDiagnostics = {
  localOrgId: string | null;
  /** Value sent as `x-feedfoundry-org-id` (empty means server default org). */
  effectiveOrgHeader: string | null;
  proxyUrl: string;
  httpStatus: number;
  rawBody: string;
  parsedJson: unknown | null;
  mappedCode: ClientErrorCode | null;
  /** One-line classification for operators (no secrets). */
  outcomeSummary: string;
};

function summarizeCreditsLoad(ok: boolean, status: number, code: ClientErrorCode | null): string {
  if (ok) return "200 — credits payload OK";
  if (code === "network_unreachable" && status === 502) return "502 — Next proxy could not reach upstream API URL";
  if (status === 0 && code === "network_unreachable") return "0 — browser could not reach /api/ff (network or CORS)";
  if (code === "unauthorized") return "401 — upstream rejected internal API key (check FEEDFOUNDRY_INTERNAL_API_KEY)";
  if (code === "forbidden") return "403 — upstream denied this org or scope";
  if (code === "annual_access_required") return "403/404 — annual archive access required";
  if (code === "annual_access_not_configured") return "404 — annual archive access not configured for org";
  if (code === "insufficient_processing_time") return "400 — insufficient processing time";
  if (code === "insufficient_credits") return "400 — insufficient processing credits";
  if (code === "server_misconfigured") return "500 — Next server env incomplete (API base or internal key)";
  if (code === "proxy_handler_error") return "502 — Next proxy threw while handling the request";
  if (code === "upstream_error") return `${status} — FeedFoundry API server error`;
  if (code === "not_found") return "404 — not found (other)";
  if (code === "bad_request") return "400 — bad request (other)";
  if (code) return `${status} — ${code}`;
  return `${status} — unknown`;
}

/**
 * Loads account credits with full diagnostics for the Dashboard (protected route).
 * Distinguishes network/proxy failures from HTTP error bodies.
 */
export async function browserGetAccountCreditsWithDiagnostics(
  orgId: string | null,
): Promise<
  | { ok: true; data: AccountCreditsResponse; diagnostics: AccountCreditsLoadDiagnostics }
  | { ok: false; error: ClientError; diagnostics: AccountCreditsLoadDiagnostics }
> {
  const path = "/v1/account/credits";
  const proxyPath = `${API_PREFIX}${path}`;
  const headers: HeadersInit = { ...orgHeaders(orgId) };
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const proxyUrl = origin ? `${origin}${proxyPath}` : proxyPath;

  let res: Response;
  try {
    res = await fetch(proxyPath, { headers, cache: "no-store" });
  } catch (e) {
    const err: ClientError = {
      code: "network_unreachable",
      status: 0,
      message: "The app could not reach the FeedFoundry API.",
      detail: String(e),
    };
    return {
      ok: false,
      error: err,
      diagnostics: {
        localOrgId: orgId,
        effectiveOrgHeader: orgId?.trim() || null,
        proxyUrl,
        httpStatus: 0,
        rawBody: "",
        parsedJson: null,
        mappedCode: err.code,
        outcomeSummary: summarizeCreditsLoad(false, 0, err.code),
      },
    };
  }

  const text = await res.text();
  let parsedJson: unknown = null;
  try {
    parsedJson = JSON.parse(text) as unknown;
  } catch {
    /* leave null */
  }

  const detail = extractFastApiDetail(text);
  const baseDiag: AccountCreditsLoadDiagnostics = {
    localOrgId: orgId,
    effectiveOrgHeader: orgId?.trim() || null,
    proxyUrl,
    httpStatus: res.status,
    rawBody: text,
    parsedJson,
    mappedCode: null,
    outcomeSummary: "",
  };

  if (!res.ok) {
    const error = mapUpstreamError(res.status, detail);
    return {
      ok: false,
      error,
      diagnostics: {
        ...baseDiag,
        mappedCode: error.code,
        outcomeSummary: summarizeCreditsLoad(false, res.status, error.code),
      },
    };
  }

  try {
    const data = JSON.parse(text) as AccountCreditsResponse;
    return {
      ok: true,
      data,
      diagnostics: { ...baseDiag, outcomeSummary: summarizeCreditsLoad(true, res.status, null) },
    };
  } catch {
    const error: ClientError = {
      code: "upstream_error",
      status: res.status,
      message: "Invalid JSON from API",
      detail,
    };
    return {
      ok: false,
      error,
      diagnostics: {
        ...baseDiag,
        mappedCode: error.code,
        outcomeSummary: summarizeCreditsLoad(false, res.status, error.code),
      },
    };
  }
}

export async function browserGet<T>(path: string, orgId: string | null): Promise<{ ok: true; data: T } | { ok: false; error: ClientError }> {
  const p = path.startsWith("/") ? path : `/${path}`;
  const res = await fetch(`${API_PREFIX}${p}`, {
    headers: { ...orgHeaders(orgId) },
    cache: "no-store",
  });
  return parseJson<T>(res);
}

export async function browserPost<T>(
  path: string,
  body: unknown,
  orgId: string | null,
): Promise<{ ok: true; data: T } | { ok: false; error: ClientError }> {
  const p = path.startsWith("/") ? path : `/${path}`;
  const res = await fetch(`${API_PREFIX}${p}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...orgHeaders(orgId),
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  return parseJson<T>(res);
}
