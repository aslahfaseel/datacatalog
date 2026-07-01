variable "project_id" {
  description = "The GCP project ID where the Cloud Run Job and Scheduler will be deployed."
  type        = string
}

variable "location" {
  description = "The GCP region for Cloud Run Job (e.g., 'us-central1')."
  type        = string
}

variable "job_name" {
  description = "The name of the Cloud Run Job."
  type        = string
  default     = "vz-aspect-patcher"
}

variable "container_image" {
  description = "The full Docker container image URI to run (e.g., 'gcr.io/project/image:tag')."
  type        = string
}

variable "service_account_email" {
  description = "The service account email the Cloud Run Job will run as."
  type        = string
}

variable "gcs_bucket_name" {
  description = "The name of the GCS bucket where the aspect assignment CSV file is stored."
  type        = string
}

variable "gcs_csv_path" {
  description = "The path inside the GCS bucket to the CSV file (e.g., 'data/vz_aspect_assignment.csv')."
  type        = string
  default     = "data/vz_aspect_assignment.csv"
}

variable "dataplex_project_id" {
  description = "The project ID where Dataplex catalog entries live (usually same as project_id)."
  type        = string
}

variable "labels" {
  description = "A map of labels to attach to the Cloud Run Job."
  type        = map(string)
  default     = {}
}

variable "max_retries" {
  description = "Number of times to retry the job if it fails."
  type        = number
  default     = 3
}

variable "timeout_seconds" {
  description = "The maximum time in seconds the job task is allowed to run before it is killed."
  type        = number
  default     = 3600
}

# ── Pipeline 2: Data Classification (manager's code) ─────────────────────────

variable "governance_project" {
  description = "The GCP project ID where DLP results and mapping tables are stored."
  type        = string
}

variable "curated_project" {
  description = "The GCP project ID where the recommended_classification staging table lives."
  type        = string
}

variable "dlp_results_table" {
  description = "Full BigQuery path to the SDP/DLP column profile results table."
  type        = string
}

variable "mapping_table" {
  description = "Full BigQuery path to the infotype_mapping_local reference table."
  type        = string
}

variable "recommended_table" {
  description = "Full BigQuery path to the recommended_classification staging table (output)."
  type        = string
}
