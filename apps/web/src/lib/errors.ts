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

export function mapUpstreamError(
  status: number,
  detail: string | undefined,
  parsed?: { flatCode?: string; flatMessage?: string; haystack: string },
): ClientError {
  const d = parsed?.haystack ?? (detail || "").toLowerCase();
  const apiMsg = parsed?.flatMessage?.trim();

  if (status === 401) {
    return { code: "unauthorized", status, message: "Session or proxy authentication failed.", detail };
  }
  if (status === 403 && (d.includes("annual_archive") || d.includes("annual_access"))) {
    return {
      code: "annual_access_required",
      status,
      message: apiMsg || "Annual archive access is required for this action.",
      detail,
    };
  }
  if (status === 404 && (d.includes("annual_archive_access_not_configured") || d.includes("annual_access_not_configured"))) {
    return {
      code: "annual_access_not_configured",
      status,
      message: apiMsg || "Annual archive access is not active for this organisation yet.",
      detail,
    };
  }
  if (
    status === 400 &&
    (d.includes("insufficient_processing_allowance") ||
      d.includes("insufficient_credits") ||
      parsed?.flatCode === "insufficient_processing_allowance")
  ) {
    return {
      code: "insufficient_credits",
      status,
      message: apiMsg || "Not enough included processing time for this job.",
      detail,
    };
  }
  if (status === 409) {
    return {
      code: "bad_request",
      status,
      message: apiMsg || "This action conflicts with the current state of the resource.",
      detail,
    };
  }
  if (status === 404) {
    return {
      code: "not_found",
      status,
      message: apiMsg || "Resource not found.",
      detail,
    };
  }
  if (status === 400) {
    return {
      code: "bad_request",
      status,
      message: apiMsg || "Request could not be completed.",
      detail,
    };
  }
  if (status >= 500) {
    return {
      code: "upstream_error",
      status,
      message: apiMsg || "Backend temporarily unavailable.",
      detail,
    };
  }
  return { code: "unknown", status, message: apiMsg || "Unexpected response.", detail };
}
