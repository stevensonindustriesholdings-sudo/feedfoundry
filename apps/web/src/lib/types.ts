/** Types aligned with FastAPI OpenAPI / app.schemas.api (minimal subset). */

/** Canonical account + processing allowance (GET /v1/account, /v1/account/usage). */
export type AccountProcessingBalanceResponse = {
  annual_archive_access_status: string;
  hosting_until: string | null;
  processing_minutes_available: number;
  processing_minutes_reserved: number;
  processing_minutes_used_lifetime: number;
  processing_period_ends_on?: string | null;
  processing_hours_available: number;
  /** Deprecated aliases; may be omitted on newer responses. */
  credits_available?: number | null;
  credits_reserved?: number | null;
  credits_spent_lifetime?: number | null;
  next_credit_expiry?: string | null;
};

/** @deprecated Use AccountProcessingBalanceResponse */
export type AccountCreditsResponse = AccountProcessingBalanceResponse;

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

export type CompleteUploadRequest = {
  media_asset_id: string;
  duration_seconds?: number | null;
};

export type CompleteUploadResponse = {
  media_asset_id: string;
  status: string;
};

export type CreateJobRequest = {
  media_asset_id: string;
  requested_outputs: string[];
  distribution_targets?: string[];
};

export type CreateJobResponse = {
  job_id: string;
  status: string;
  estimated_processing_minutes: number;
  reserved_processing_minutes: number;
  estimated_processing_hours: number;
  estimated_credits?: number | null;
  reserved_credits?: number | null;
};

export type JobStatusResponse = {
  job_id: string;
  status: string;
  progress_percent: number;
  current_stage: string | null;
  estimated_processing_minutes?: number | null;
  reserved_processing_minutes?: number | null;
  actual_processing_minutes_charged?: number | null;
  estimated_processing_hours?: number | null;
  estimated_credits?: number | null;
  reserved_credits?: number | null;
  actual_credits_so_far?: number | null;
  /** Present when API exposes failure details (optional until backend extends OpenAPI). */
  failure_code?: string | null;
  failure_message?: string | null;
};

export type JobSummaryItem = {
  job_id: string;
  status: string;
  progress_percent: number;
  current_stage?: string | null;
  media_asset_id: string;
  created_at?: string | null;
};

export type JobListResponse = {
  jobs: JobSummaryItem[];
  total: number;
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

export type OutputCatalogEntryResponse = {
  output_type: string;
  title: string;
  ready: boolean;
  format?: string | null;
  download_url?: string | null;
};

export type JobOutputsCatalogResponse = {
  job_id: string;
  outputs: OutputCatalogEntryResponse[];
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

/** GET /v1/system/worker-hints — no secrets. */
export type WorkerHintsResponse = {
  ff_ai_live_calls_enabled: boolean;
  openai_configured: boolean;
  openrouter_configured: boolean;
  ai_routing_modules_loaded: number;
  youtube_source_queue_enabled: boolean;
  notes?: string;
};

export type YoutubeQueueEnqueueResponse = {
  id: string;
  youtube_url: string;
  status: string;
  detail?: string;
};

export type YoutubeQueueItemResponse = {
  id: string;
  youtube_url: string;
  status: string;
  notes?: string | null;
  created_at?: string | null;
};

export type YoutubeQueueListResponse = {
  items: YoutubeQueueItemResponse[];
  total: number;
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
