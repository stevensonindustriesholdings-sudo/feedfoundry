/**
 * Dev-only mock for GET /v1/account (and /v1/account/usage) — bypasses Railway when upstream is unavailable.
 * In `next dev`, mock is ON by default (no env to set). Opt out: FEEDFOUNDRY_USE_LIVE_ACCOUNT_CREDITS=1
 */
function truthyEnv(v: string | undefined): boolean {
  if (!v) return false;
  return ["1", "true", "yes", "on"].includes(v.toLowerCase());
}

/** Default ON in `next dev`; opt out with FEEDFOUNDRY_USE_LIVE_ACCOUNT_CREDITS=1 */
export function isDevAccountCreditsMockEnabled(): boolean {
  if (process.env.NODE_ENV !== "development") return false;
  if (truthyEnv(process.env.FEEDFOUNDRY_USE_LIVE_ACCOUNT_CREDITS)) return false;
  return true;
}

/** JSON body matching FastAPI `AccountProcessingBalanceResponse`. */
export function mockAccountCreditsJson(): string {
  const iso = new Date(Date.now() + 86400e3 * 365).toISOString().slice(0, 10);
  return JSON.stringify({
    annual_archive_access_status: "active",
    hosting_until: iso,
    processing_minutes_available: 300,
    processing_minutes_reserved: 0,
    processing_minutes_used_lifetime: 0,
    processing_period_ends_on: iso,
    processing_hours_available: 5,
    credits_available: 300,
    credits_reserved: 0,
    credits_spent_lifetime: 0,
    next_credit_expiry: iso,
  });
}
