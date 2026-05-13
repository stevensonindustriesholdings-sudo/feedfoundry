/**
 * Dev-only mock for GET /v1/account/credits — bypasses Railway when the real endpoint is broken.
 * Never enable in production deployments.
 */

function truthyEnv(v: string | undefined): boolean {
  const s = (v || "").trim().toLowerCase();
  return s === "1" || s === "true" || s === "yes";
}

/** Active only in `next dev` (NODE_ENV=development) with explicit flag. */
export function isDevAccountCreditsMockEnabled(): boolean {
  return process.env.NODE_ENV === "development" && truthyEnv(process.env.FEEDFOUNDRY_DEV_MOCK_ACCOUNT_CREDITS);
}

/** JSON body matching FastAPI `AccountCreditsResponse`. */
export function mockAccountCreditsJson(): string {
  const far = new Date();
  far.setUTCFullYear(far.getUTCFullYear() + 1);
  const iso = far.toISOString().slice(0, 10);
  return JSON.stringify({
    annual_access_status: "active",
    hosting_until: iso,
    credits_available: 300,
    credits_reserved: 0,
    credits_spent_lifetime: 0,
    next_credit_expiry: iso,
  });
}
