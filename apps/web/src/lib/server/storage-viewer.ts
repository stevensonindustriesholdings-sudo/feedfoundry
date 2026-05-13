/**
 * Server-only R2 / S3-compatible listing for the System Storage viewer.
 * Reads the same env names as `apps/api` (`R2_*`). Never import from client components.
 */

import { ListObjectsV2Command, S3Client } from "@aws-sdk/client-s3";

export const STORAGE_VIEWER_CREDENTIALS_MISSING =
  "Storage credentials not configured in local web environment.";

export type StorageObjectRow = {
  key: string;
  size: number | null;
  lastModified: string | null;
};

export type QuickFilterId = "source" | "outputs" | "media_inspection" | "raw_transcript" | "hosted_manifest";

function r2S3EndpointUrl(): string {
  const explicit = process.env.R2_ENDPOINT_URL?.trim();
  if (explicit) return explicit;
  const account = process.env.R2_ACCOUNT_ID?.trim();
  if (account) return `https://${account}.r2.cloudflarestorage.com`;
  return "";
}

function viewerBucket(): string {
  return (
    process.env.R2_STORAGE_VIEWER_BUCKET?.trim() ||
    process.env.R2_BUCKET_SOURCE?.trim() ||
    process.env.R2_BUCKET_OUTPUTS?.trim() ||
    "feedfoundry-storage"
  );
}

function credentialsConfigured(): boolean {
  const endpoint = r2S3EndpointUrl();
  const keyId = process.env.R2_ACCESS_KEY_ID?.trim();
  const secret = process.env.R2_SECRET_ACCESS_KEY?.trim();
  return !!(endpoint && keyId && secret);
}

function buildClient(): S3Client | null {
  if (!credentialsConfigured()) return null;
  const endpoint = r2S3EndpointUrl();
  const region = (process.env.R2_REGION?.trim() || "auto") || "auto";
  return new S3Client({
    region,
    endpoint,
    credentials: {
      accessKeyId: process.env.R2_ACCESS_KEY_ID!.trim(),
      secretAccessKey: process.env.R2_SECRET_ACCESS_KEY!.trim(),
    },
    forcePathStyle: true,
  });
}

export function isQuickFilter(s: string | undefined): s is QuickFilterId {
  return (
    s === "source" ||
    s === "outputs" ||
    s === "media_inspection" ||
    s === "raw_transcript" ||
    s === "hosted_manifest"
  );
}

export function applyQuickFilter(rows: StorageObjectRow[], filter: string | undefined): StorageObjectRow[] {
  if (!filter || !isQuickFilter(filter)) return rows;
  switch (filter) {
    case "source":
      return rows.filter((r) => r.key.includes("/source/"));
    case "outputs":
      return rows.filter((r) => r.key.includes("/outputs/"));
    case "media_inspection":
      return rows.filter((r) => r.key.includes("media_inspection.json"));
    case "raw_transcript":
      return rows.filter((r) => r.key.endsWith("transcript.json"));
    case "hosted_manifest":
      return rows.filter((r) => r.key.includes("hosted_manifest.json"));
    default:
      return rows;
  }
}

export type ListStorageResult =
  | {
      ok: true;
      bucket: string;
      prefix: string;
      objects: StorageObjectRow[];
      isTruncated: boolean;
      nextContinuationToken: string | undefined;
    }
  | { ok: false; message: string };

const PAGE_SIZE = 500;

export async function listStorageObjects(params: {
  prefix: string;
  continuationToken?: string | null;
}): Promise<ListStorageResult> {
  if (!credentialsConfigured()) {
    return { ok: false, message: STORAGE_VIEWER_CREDENTIALS_MISSING };
  }

  const bucket = viewerBucket();
  const client = buildClient();
  if (!client) {
    return { ok: false, message: STORAGE_VIEWER_CREDENTIALS_MISSING };
  }

  const prefix = params.prefix;
  try {
    const out = await client.send(
      new ListObjectsV2Command({
        Bucket: bucket,
        Prefix: prefix === "" ? undefined : prefix,
        ContinuationToken: params.continuationToken || undefined,
        MaxKeys: PAGE_SIZE,
      }),
    );

    const objects: StorageObjectRow[] =
      out.Contents?.map((c) => ({
        key: c.Key ?? "",
        size: typeof c.Size === "number" ? c.Size : null,
        lastModified: c.LastModified ? c.LastModified.toISOString() : null,
      })).filter((r) => r.key.length > 0) ?? [];

    return {
      ok: true,
      bucket,
      prefix,
      objects,
      isTruncated: !!out.IsTruncated,
      nextContinuationToken: out.NextContinuationToken,
    };
  } catch (e) {
    const msg = (e as Error).message || String(e);
    return { ok: false, message: msg };
  }
}

export function storageViewerBucketNameForDisplay(): string {
  return viewerBucket();
}
