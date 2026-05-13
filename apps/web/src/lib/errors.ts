export type ClientErrorCode =
  | "unauthorized"
  | "insufficient_credits"
  | "annual_access_required"
  | "annual_access_not_configured"
  | "outputs_not_ready"
  | "not_found"
  | "bad_request"
  | "upstream_error"
  | "unknown";

export type ClientError = {
  code: ClientErrorCode;
  status: number;
  message: string;
  detail?: string;
};

export function mapUpstreamError(status: number, detail: string | undefined): ClientError {
  const d = (detail || "").toLowerCase();

  if (status === 401) {
    return { code: "unauthorized", status, message: "Session or proxy authentication failed.", detail };
  }
  if (status === 403 && d.includes("annual_access")) {
    return {
      code: "annual_access_required",
      status,
      message: "Annual archive access is required for this action.",
      detail,
    };
  }
  if (status === 404 && d.includes("annual_access_not_configured")) {
    return {
      code: "annual_access_not_configured",
      status,
      message: "Annual archive access is not active for this organisation yet.",
      detail,
    };
  }
  if (status === 400 && d.includes("insufficient_credits")) {
    return {
      code: "insufficient_credits",
      status,
      message: "Not enough included processing time for this job.",
      detail,
    };
  }
  if (status === 404) {
    return { code: "not_found", status, message: "Resource not found.", detail };
  }
  if (status === 400) {
    return { code: "bad_request", status, message: "Request could not be completed.", detail };
  }
  if (status >= 500) {
    return { code: "upstream_error", status, message: "Backend temporarily unavailable.", detail };
  }
  return { code: "unknown", status, message: "Unexpected response.", detail };
}
