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

variable "aspect_patcher_gcs_bucket" {
  description = "The GCS bucket name where the vz_aspect_assignment.csv file is stored."
  type        = string
  default     = "vz-datacatalog"
}

variable "bulk_aspect_apply_tag" {
  description = "The container image tag for the bulk aspect apply job."
  type        = string
  default     = "latest"
}

variable "profiler_tag" {
  description = "The container image tag for the profiler job."
  type        = string
  default     = "latest"
}

variable "trust_score_tag" {
  description = "The container image tag for the trust score job."
  type        = string
  default     = "latest"
}

