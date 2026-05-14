/** Parse API error bodies: canonical flat `{ code, message, fields }` or legacy shapes. */

export type ParsedUpstreamError = {
  flatCode?: string;
  flatMessage?: string;
  /** Lowercased string used for heuristic matching (legacy). */
  haystack: string;
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function parseUpstreamErrorJson(text: string): ParsedUpstreamError {
  let haystack = text.toLowerCase();
  let flatCode: string | undefined;
  let flatMessage: string | undefined;
  try {
    const j = JSON.parse(text) as unknown;
    if (!isRecord(j)) return { haystack };
    if (typeof j.code === "string" && typeof j.message === "string") {
      flatCode = j.code;
      flatMessage = j.message;
      haystack = `${flatCode} ${flatMessage}`.toLowerCase();
      return { flatCode, flatMessage, haystack };
    }
    const detail = j.detail;
    if (typeof detail === "string") {
      haystack = `${detail} ${haystack}`.toLowerCase();
      return { haystack };
    }
    if (isRecord(detail) && typeof detail.code === "string" && typeof detail.message === "string") {
      flatCode = detail.code;
      flatMessage = detail.message;
      haystack = `${flatCode} ${flatMessage}`.toLowerCase();
      return { flatCode, flatMessage, haystack };
    }
  } catch {
    /* leave haystack from raw text */
  }
  return { haystack };
}
