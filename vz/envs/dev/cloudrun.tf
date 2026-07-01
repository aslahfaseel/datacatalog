module "cloudrun_aspect_patcher" {
  source = "../../custom_modules/cloudrun_aspect"

  project_id  = var.project_id
  location    = var.location

  job_name              = "vz-aspect-patcher"
  container_image       = var.aspect_patcher_image
  service_account_email = var.terraform_sa

  # Pipeline 1: Asset Governance (reads CSV from GCS)
  gcs_bucket_name     = var.aspect_patcher_gcs_bucket
  gcs_csv_path        = "data/vz_aspect_assignment.csv"
  dataplex_project_id = var.project_id

  # Pipeline 2: Data Classification (reads DLP results from BigQuery)
  governance_project = var.project_id
  curated_project    = var.project_id
  dlp_results_table  = "${var.project_id}.vzdataset.sdp_results"
  mapping_table      = "${var.project_id}.vzdataset.infotype_mapping_local"
  recommended_table  = "${var.project_id}.vzdataset.recommended_classification"

  max_retries     = 3
  timeout_seconds = 3600

  labels = {
    project     = "vz"
    environment = "dev"
    managed_by  = "terraform"
    purpose     = "aspect-patcher"
  }

}


