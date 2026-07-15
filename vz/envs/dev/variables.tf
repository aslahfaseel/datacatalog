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

variable "dq_profile_scans" {
  description = "config mapping"
  type        = any
  default     = {}  
}

variable "aspect_patcher_gcs_bucket" {
  description = "GCS bucket for bulk apply"
  type        = string
   default     = "aspect-application-poc-bucket"
}
