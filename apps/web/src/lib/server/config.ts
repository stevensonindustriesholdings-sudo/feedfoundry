/**
 * Server-only configuration. Do not import from client components.
 */
export function getServerConfig() {
  const apiBase = process.env.FEEDFOUNDRY_API_BASE_URL?.replace(/\/$/, "") || "";
  const internalKey = process.env.FEEDFOUNDRY_INTERNAL_API_KEY || "";
  const defaultOrgId = process.env.FEEDFOUNDRY_DEFAULT_ORG_ID || "org_dev_demo";

  if (!apiBase) {
    throw new Error("FEEDFOUNDRY_API_BASE_URL is not set");
  }
  if (!internalKey) {
    throw new Error("FEEDFOUNDRY_INTERNAL_API_KEY is not set");
  }

  return { apiBase, internalKey, defaultOrgId };
}
