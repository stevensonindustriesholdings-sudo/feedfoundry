/**
 * Server-only configuration. Do not import from client components.
 *
 * Railway (and other hosts) inject secrets at container runtime. Next may inline
 * `process.env.FOO` at build time when `FOO` is absent during `next build`, which
 * would freeze those values as empty. Use dynamic keys so runtime env is honored.
 */
function runtimeEnv(nameParts: string[]): string {
  const key = nameParts.join("_");
  const raw = process.env[key];
  return typeof raw === "string" ? raw.trim() : "";
}

export function getServerConfig() {
  const apiBase = runtimeEnv(["FEEDFOUNDRY", "API", "BASE", "URL"]).replace(/\/$/, "");
  const internalKey = runtimeEnv(["FEEDFOUNDRY", "INTERNAL", "API", "KEY"]);
  const defaultOrgId =
    runtimeEnv(["FEEDFOUNDRY", "DEFAULT", "ORG", "ID"]) || "org_dev_demo";

  if (!apiBase) {
    throw new Error("FEEDFOUNDRY_API_BASE_URL is not set");
  }
  if (!internalKey) {
    throw new Error("FEEDFOUNDRY_INTERNAL_API_KEY is not set");
  }

  return { apiBase, internalKey, defaultOrgId };
}
