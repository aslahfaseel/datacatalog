variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "location" {
  type    = string
  default = "us-central1"
}

variable "terraform_sa" {
  type = string
}

variable "dataplex_service_agent" {
  type = string
}

variable "alert_emails" {
  type    = list(string)
  default = []
}

# ── Cloud Run image tags ────────────────────────────────────────────────────

variable "trust_score_tag" {
  description = "Image tag for Trust Score"
  type        = string
  default     = "latest"
}

variable "bulk_aspect_apply_tag" {
  description = "Image tag for Bulk Aspect Apply"
  type        = string
  default     = "latest"
}

variable "profiler_cloud_run_tag" {
  description = "Image tag for Profiler"
  type        = string
  default     = "latest"
}

# ── GCS bucket (holds all 3 CSV files) ─────────────────────────────────────
# ▼▼▼ CLIENT ENV: set this to your GCS bucket name ▼▼▼

variable "gcs_bucket_name" {
  description = "GCS bucket that holds profiling.csv, custom_dq.csv, profile_based_dq.csv"
  type        = string
  default     = "vz-datacatalog"
}
