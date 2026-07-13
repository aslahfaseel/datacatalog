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

# Cloud Run Aspect Patcher variables
variable "aspect_patcher_image" {
  description = "The full Docker image URI for the Cloud Run aspect patcher job (e.g. gcr.io/project/vz-aspect-patcher:latest)."
  type        = string
  default     = "gcr.io/dmgcp-del-181/vz-aspect-patcher:latest"
}

variable "aspect_patcher_gcs_bucket" {
  description = "The GCS bucket name where the vz_aspect_assignment.csv file is stored."
  type        = string
  default     = "vz-datacatalog"
}
