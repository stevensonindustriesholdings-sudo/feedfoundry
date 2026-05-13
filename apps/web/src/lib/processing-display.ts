/**
 * Customer-facing copy uses **processing minutes / hours**, not the word "credits".
 *
 * Upstream responses still use `credits_*` / `*_credits` field names (OpenAPI).
 * TODO(api-contract): Have GET `/v1/account/credits` and job payloads expose explicit
 * `processing_seconds_remaining` (or similar) and remove this mapping assumption.
 */
export const ASSUMED_PROCESSING_MINUTES_PER_API_UNIT = 1;

export function processingMinutesFromApiUnits(units: number): number {
  return Math.max(0, Math.round(units * ASSUMED_PROCESSING_MINUTES_PER_API_UNIT));
}

/** Formats whole minutes for UI, e.g. `42 min` or `2 hr 15 min`. */
export function formatProcessingAllowanceMinutes(totalMinutes: number): string {
  const n = Math.max(0, Math.round(totalMinutes));
  if (n === 0) return "0 min";
  if (n < 60) return `${n} min`;
  const h = Math.floor(n / 60);
  const min = n % 60;
  if (min === 0) return `${h} hr`;
  return `${h} hr ${min} min`;
}

export function formatApiUnitsAsProcessing(units: number | null | undefined): string {
  if (units === null || units === undefined) return "—";
  return formatProcessingAllowanceMinutes(processingMinutesFromApiUnits(units));
}
