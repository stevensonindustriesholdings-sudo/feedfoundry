"use client";

const ORG_KEY = "ff_org_id";
const JOB_KEY = "ff_latest_job_id";

export function getOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ORG_KEY);
}

export function setOrgId(id: string) {
  localStorage.setItem(ORG_KEY, id);
}

export function clearOrgId() {
  localStorage.removeItem(ORG_KEY);
}

export function getLatestJobId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(JOB_KEY);
}

export function setLatestJobId(id: string) {
  localStorage.setItem(JOB_KEY, id);
}
