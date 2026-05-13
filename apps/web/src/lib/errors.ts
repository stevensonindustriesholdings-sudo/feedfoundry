export type ClientErrorCode =
  | "unauthorized"
  | "insufficient_credits"
  | "insufficient_processing_time"
  | "annual_access_required"
  | "annual_access_not_configured"
  | "outputs_not_ready"
  | "not_found"
  | "bad_request"
  | "forbidden"
  | "server_misconfigured"
  | "proxy_handler_error"
  | "upstream_error"
  | "network_unreachable"
  | "unknown";

export type ClientError = {
  code: ClientErrorCode;
  status: number;
  message: string;
  detail?: string;
};

/**
 * Maps HTTP responses from `/api/ff/*` (proxy) or upstream-shaped JSON to stable client codes.
 * Avoid vague "backend unavailable" for HTTP errors — reserve that for real transport failures.
 */
export function mapUpstreamError(status: number, detail: string | undefined): ClientError {
  const d = (detail || "").toLowerCase();

  if (status === 401) {
    return { code: "unauthorized", status, message: "Upstream returned 401 (invalid or missing internal API key).", detail };
  }

  if (status === 403 && d.includes("annual_access")) {
    return {
      code: "annual_access_required",
      status,
      message: "Upstream returned 403 (annual archive access required).",
      detail,
    };
  }
  if (status === 403) {
    return {
      code: "forbidden",
      status,
      message: "Upstream returned 403 (forbidden).",
      detail,
    };
  }

  if (status === 404 && d.includes("annual_access_required")) {
    return {
      code: "annual_access_required",
      status,
      message: "Upstream returned 404 with annual_access_required.",
      detail,
    };
  }
  if (status === 404 && d.includes("annual_access_not_configured")) {
    return {
      code: "annual_access_not_configured",
      status,
      message: "Upstream returned 404 (annual archive access not configured for this org).",
      detail,
    };
  }

  if (status === 400 && d.includes("insufficient_credits")) {
    return {
      code: "insufficient_credits",
      status,
      message: "Upstream returned 400 (insufficient processing credits).",
      detail,
    };
  }

  if (status === 400 && d.includes("insufficient_processing_time")) {
    return {
      code: "insufficient_processing_time",
      status,
      message: "Upstream returned 400 (not enough processing time for this upload).",
      detail,
    };
  }

  if (status === 404) {
    return { code: "not_found", status, message: "Upstream returned 404 (not found).", detail };
  }
  if (status === 400) {
    return { code: "bad_request", status, message: "Upstream returned 400 (bad request).", detail };
  }

  if (status === 502 && d.includes("proxy_upstream_unreachable")) {
    return {
      code: "network_unreachable",
      status,
      message: "Next proxy could not connect to FEEDFOUNDRY_API_BASE_URL.",
      detail,
    };
  }
  if (status === 502 && d.includes("proxy_handler_error")) {
    return {
      code: "proxy_handler_error",
      status,
      message: "Next proxy threw while forwarding (see proxy logs / message).",
      detail,
    };
  }
  if (status === 502) {
    return {
      code: "upstream_error",
      status,
      message: "HTTP 502 from local proxy or upstream (see response body).",
      detail,
    };
  }

  if (
    status === 500 &&
    (d.includes("server_misconfigured") ||
      d.includes("feedfoundry_api_base_url") ||
      d.includes("feedfoundry_internal_api_key") ||
      d.includes("is not set"))
  ) {
    return {
      code: "server_misconfigured",
      status,
      message: "Next server env is incomplete (FEEDFOUNDRY_API_BASE_URL or FEEDFOUNDRY_INTERNAL_API_KEY).",
      detail,
    };
  }

  if (status >= 500) {
    return {
      code: "upstream_error",
      status,
      message: `FeedFoundry API returned HTTP ${status} (server error).`,
      detail,
    };
  }

  return { code: "unknown", status, message: `Unexpected HTTP ${status}.`, detail };
}
