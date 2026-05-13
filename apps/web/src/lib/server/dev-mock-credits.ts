/**
 * Dev-only mock for GET /v1/account/credits — bypasses Railway when the real endpoint is broken.
 * In `next dev`, mock is ON by default (no env to set). Opt out: FEEDFOUNDRY_USE_LIVE_ACCOUNT_CREDITS=1
 * Never used in production (`next start` / NODE_ENV=production).
 */

function truthyEnv(v: string | undefined): boolean {
  const s = (v || "").trim().toLowerCase();
  return s === "1" || s === "true" || s === "yes";
}

/** Default ON in `next dev`; opt out with FEEDFOUNDRY_USE_LIVE_ACCOUNT_CREDITS=1 */
export function isDevAccountCreditsMockEnabled(): boolean {
  if (process.env.NODE_ENV !== "development") return false;
  if (truthyEnv(process.env.FEEDFOUNDRY_USE_LIVE_ACCOUNT_CREDITS)) return false;
  return true;
}

/** JSON body matching FastAPI `AccountCreditsResponse`. */
export function mockAccountCreditsJson(): string {
  const far = new Date();
  far.setUTCFullYear(far.getUTCFullYear() + 1);
  const iso = far.toISOString().slice(0, 10);
  return JSON.stringify({
    annual_access_status: "active",
    hosting_until: iso,
    processing_minutes_available: 300,
    processing_minutes_reserved: 0,
    processing_minutes_used_lifetime: 0,
    goodwill_processing_minutes_granted_ytd: 0,
    next_processing_period_end: iso,
    credits_available: 300,
    credits_reserved: 0,
    credits_spent_lifetime: 0,
    next_credit_expiry: iso,
  });
}
