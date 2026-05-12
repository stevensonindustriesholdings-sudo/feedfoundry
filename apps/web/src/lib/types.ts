/** Types aligned with FastAPI OpenAPI / app.schemas.api (minimal subset). */

export type AccountCreditsResponse = {
  annual_access_status: string;
  hosting_until: string | null;
  credits_available: number;
  credits_reserved: number;
  credits_spent_lifetime: number;
  next_credit_expiry: string | null;
};

export type PresignUploadRequest = {
  filename: string;
  content_type: string;
  file_size_bytes: number;
  media_type: string;
};

export type PresignUploadResponse = {
  media_asset_id: string;
  upload_url: string;
  storage_key: string;
  expires_in_seconds: number;
};

export type CreateJobRequest = {
  media_asset_id: string;
  requested_outputs: string[];
  distribution_targets?: string[];
};

export type CreateJobResponse = {
  job_id: string;
  status: string;
  estimated_credits: number;
  reserved_credits: number;
};

export type JobStatusResponse = {
  job_id: string;
  status: string;
  progress_percent: number;
  current_stage: string | null;
  estimated_credits: number | null;
  reserved_credits: number | null;
  actual_credits_so_far?: number | null;
};

export type OutputItemResponse = {
  type: string;
  title: string;
  format: string;
  download_url: string;
};

export type JobOutputsResponse = {
  job_id: string;
  outputs: OutputItemResponse[];
};

/** Hosted manifest JSON — shape varies; keep loose for UI. */
export type ManifestResponse = Record<string, unknown>;

export type HealthResponse = {
  status: string;
  service: string;
  timestamp?: string;
};

export type ReadyResponse = {
  ready: boolean;
  environment?: string;
  strict_validation?: boolean;
  checks?: Record<string, unknown>;
};

export const OUTPUT_OPTIONS = [
  { id: "transcript", label: "Transcript" },
  { id: "clean_transcript", label: "Clean transcript" },
  { id: "chapters", label: "Chapters" },
  { id: "clip_candidates", label: "Clip candidates" },
  { id: "show_notes", label: "Show notes" },
  { id: "metadata", label: "Metadata" },
  { id: "ctas", label: "CTAs" },
  { id: "fact_sheet", label: "Fact sheet" },
  { id: "faqs", label: "FAQs" },
  { id: "hosted_manifest", label: "Hosted manifest" },
  { id: "export_bundle", label: "Export bundle" },
] as const;
