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

# Map of profile-based DQ scans — add one entry per table to scale to 50 tables
# existing_profile_scan_id = the profiling scan that already ran and generated recommendations
# new_dq_scan_id           = the new DQ scan Terraform will create
variable "dq_profile_scans" {
  description = "Map of DQ scans to create from profile recommendations. Key = logical name."
  type = map(object({
    project_id               = string
    region                   = string
    existing_profile_scan_id = string
    new_dq_scan_id           = string
  }))
  default = {}
}

# Cloud Run Aspect Patcher variables
variable "aspect_patcher_image" {
  description = "The full Docker image URI for the Cloud Run aspect patcher job (e.g. gcr.io/project/vz-aspect-patcher:latest)."
  type        = string
  default     = "python:3.11-slim"
}

variable "aspect_patcher_gcs_bucket" {
  description = "The GCS bucket name where the vz_aspect_assignment.csv file is stored."
  type        = string
  default     = "vz-datacatalog"
}
