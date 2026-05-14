/**
 * Customer-facing copy uses **processing minutes / hours**, not the word "credits".
 *
 * GET `/v1/account` exposes `processing_minutes_*` fields. Job payloads expose
 * `estimated_processing_minutes` (legacy `*_credits` aliases may still appear).
 * Numeric API units are treated as whole minutes for display rounding.
 */
export const ASSUMED_PROCESSING_MINUTES_PER_API_UNIT = 1;

export function processingMinutesFromApiUnits(units: number): number {
  return Math.max(0, Math.round(units * ASSUMED_PROCESSING_MINUTES_PER_API_UNIT));
}

/** Prefer canonical processing-minutes fields; fall back to deprecated credit-named aliases. */
export function jobEstimateMinutes(
  primary: number | null | undefined,
  legacyAlias: number | null | undefined,
): number | null | undefined {
  if (primary != null) return primary;
  return legacyAlias;
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
