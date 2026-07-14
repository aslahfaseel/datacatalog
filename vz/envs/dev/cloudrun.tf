locals {
  base_image_uri = "us-east4-docker.pkg.dev/vz-it-np-keiv-dev-dpev-0/vz-it-keiv-dpev-0-docker"
}

module "cloudrun_bulk_aspect_apply" {
  source = "../../custom_modules/cloudrun_job"

  project_id            = var.project_id
  location              = var.location
  job_name              = "vz-aspect-patcher"
  container_image       = "${local.base_image_uri}/bulk_aspect_apply:${var.image_tag}"
  service_account_email = var.terraform_sa
  
  max_retries     = 3
  timeout_seconds = 3600

  env_vars = {
    GCS_BUCKET_NAME    = var.aspect_patcher_gcs_bucket
    GCS_CSV_PATH       = "data/vz_aspect_assignment.csv"
    DATAPLEX_PROJECT_ID = var.project_id
    DATAPLEX_LOCATION  = var.location
    GOVERNANCE_PROJECT = var.project_id
    CURATED_PROJECT    = var.project_id
    DLP_RESULTS_TABLE  = "${var.project_id}.vzdataset.sdp_results"
    MAPPING_TABLE      = "${var.project_id}.vzdataset.infotype_mapping_local"
    RECOMMENDED_TABLE  = "${var.project_id}.vzdataset.recommended_classification"
  }

  labels = {
    purpose = "aspect-patcher"
  }
}

module "cloudrun_profiler" {
  source = "../../custom_modules/cloudrun_job"

  project_id            = var.project_id
  location              = var.location
  job_name              = "vz-profiler-job"
  container_image       = "${local.base_image_uri}/profiler_cloud_run:${var.image_tag}"
  service_account_email = var.terraform_sa

  env_vars = {
    CONFIG_GCS_URI = "gs://vz-datacatalog/data/profiler_config.yaml"
  }

  labels = {
    purpose = "data-profiler"
  }
}

module "cloudrun_trust_score" {
  source = "../../custom_modules/cloudrun_job"

  project_id            = var.project_id
  location              = var.location
  job_name              = "vz-trust-score"
  container_image       = "${local.base_image_uri}/trust_score:${var.image_tag}"
  service_account_email = var.terraform_sa

  env_vars = {
    TRUST_CONFIG_URI = "gs://vz-datacatalog/data/trust_score_config.json"
  }

  labels = {
    purpose = "trust-score"
  }
}

