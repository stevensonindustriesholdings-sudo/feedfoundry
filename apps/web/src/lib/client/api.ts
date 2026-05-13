import type { ClientError } from "../errors";
import { mapUpstreamError } from "../errors";
import { parseUpstreamErrorJson } from "./errors-parse";

const API_PREFIX = "/api/ff";

function orgHeaders(orgId: string | null): HeadersInit {
  const h: Record<string, string> = {};
  if (orgId) h["x-feedfoundry-org-id"] = orgId;
  return h;
}

async function parseJson<T>(res: Response): Promise<{ ok: true; data: T } | { ok: false; error: ClientError }> {
  const text = await res.text();
  let detail: string | undefined;
  try {
    const j = JSON.parse(text) as { detail?: string };
    detail = typeof j.detail === "string" ? j.detail : undefined;
  } catch {
    /* ignore */
  }
  if (!res.ok) {
    const parsed = parseUpstreamErrorJson(text);
    return { ok: false, error: mapUpstreamError(res.status, detail, parsed) };
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
