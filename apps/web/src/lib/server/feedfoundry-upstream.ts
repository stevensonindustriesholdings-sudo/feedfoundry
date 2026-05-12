import { getServerConfig } from "./config";

const ORG_HEADER = "X-Org-Id";

export type ForwardOptions = {
  method?: string;
  body?: string | undefined;
  orgId?: string | null;
  /** Extra headers (e.g. Content-Type for POST) */
  headers?: Record<string, string>;
};

/**
 * Forward a request to the FeedFoundry API with server-side credentials.
 * Path must start with / (e.g. /v1/account/credits).
 */
export async function forwardToFeedFoundry(
  path: string,
  options: ForwardOptions = {},
): Promise<Response> {
  const { apiBase, internalKey, defaultOrgId } = getServerConfig();
  const url = `${apiBase}${path.startsWith("/") ? path : `/${path}`}`;
  const orgId = options.orgId?.trim() || defaultOrgId;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${internalKey}`,
    [ORG_HEADER]: orgId,
    ...options.headers,
  };

  return fetch(url, {
    method: options.method || "GET",
    headers,
    body: options.body,
    cache: "no-store",
  });
}
