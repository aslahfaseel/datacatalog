module "cloudrun_aspect_patcher" {
  source = "../../custom_modules/cloudrun_aspect_patcher"

  project_id  = var.project_id
  location    = var.location

  job_name              = "vz-aspect-patcher"
  container_image       = var.aspect_patcher_image
  service_account_email = var.terraform_sa

  # Using the existing 'vz-datacatalog' GCS bucket to store the CSV
  gcs_bucket_name     = var.aspect_patcher_gcs_bucket
  gcs_csv_path        = "data/vz_aspect_assignment.csv"
  dataplex_project_id = var.project_id

  max_retries     = 3
  timeout_seconds = 3600

  labels = {
    project     = "vz"
    environment = "dev"
    managed_by  = "terraform"
    purpose     = "aspect-patcher"
  }

  depends_on = [module.dataplex_iam]
}
