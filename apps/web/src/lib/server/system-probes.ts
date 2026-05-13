import { headers } from "next/headers";

import { getServerConfig } from "./config";
import { isDevAccountCreditsMockEnabled, mockAccountCreditsJson } from "./dev-mock-credits";
import { forwardToFeedFoundry } from "./feedfoundry-upstream";

export type SimpleProbe = {
  url: string;
  httpStatus: number;
  ok: boolean;
  snippet: string;
  error?: string;
};

function trimSnippet(text: string, max = 600): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

/** GET {publicBase}/health — no secrets (public liveness). */
export async function probePublicHealth(publicBase: string): Promise<SimpleProbe> {
  const base = publicBase.replace(/\/$/, "");
  const url = `${base}/health`;
  try {
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    return { url, httpStatus: res.status, ok: res.ok, snippet: trimSnippet(text) };
  } catch (e) {
    return { url, httpStatus: 0, ok: false, snippet: "", error: (e as Error).message };
  }
}

/** GET {publicBase}/ready — no secrets. */
export async function probePublicReady(publicBase: string): Promise<SimpleProbe> {
  const base = publicBase.replace(/\/$/, "");
  const url = `${base}/ready`;
  try {
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    return { url, httpStatus: res.status, ok: res.ok, snippet: trimSnippet(text) };
  } catch (e) {
    return { url, httpStatus: 0, ok: false, snippet: "", error: (e as Error).message };
  }
}

/**
 * GET `/v1/account/credits` upstream using the same server credentials as `/api/ff/*` (no loopback fetch).
 */
export async function probeProxyAccountCredits(): Promise<SimpleProbe> {
  const url = "GET /v1/account/credits (server credentials, same as /api/ff proxy)";
  if (isDevAccountCreditsMockEnabled()) {
    const body = mockAccountCreditsJson();
    return {
      url: "GET /v1/account/credits (dev mock — default in next dev)",
      httpStatus: 200,
      ok: true,
      snippet: trimSnippet(body),
    };
  }
  const h = await headers();
  const orgHint = h.get("x-feedfoundry-org-id")?.trim() || null;
  try {
    const { defaultOrgId } = getServerConfig();
    const orgId = orgHint || defaultOrgId;
    const upstream = await forwardToFeedFoundry("/v1/account/credits", { method: "GET", orgId });
    const text = await upstream.text();
    return { url, httpStatus: upstream.status, ok: upstream.ok, snippet: trimSnippet(text) };
  } catch (e) {
    return { url, httpStatus: 0, ok: false, snippet: "", error: (e as Error).message };
  }
}
