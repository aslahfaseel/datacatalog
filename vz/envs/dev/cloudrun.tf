locals {
  base_image_uri = "us-east4-docker.pkg.dev/vz-it-np-keiv-dev-dpev-0/vz-it-keiv-dpev-0-docker"
  
   cloudrun_jobs = {
    "bulk-aspect-apply" = {
      image           = "bulk_aspect_apply"
      tag             = var.bulk_aspect_apply_tag
      max_retries     = 3
      timeout_seconds = 3600
      env_vars = {
        GCS_BUCKET_NAME     = var.aspect_patcher_gcs_bucket
        GCS_CSV_PATH        = "data/vz_aspect_assignment.csv"
        DATAPLEX_PROJECT_ID = var.project_id
        DATAPLEX_LOCATION   = var.location
        GOVERNANCE_PROJECT  = var.project_id
        CURATED_PROJECT     = var.project_id
        DLP_RESULTS_TABLE   = "${var.project_id}.vzdataset.sdp_results"
        MAPPING_TABLE       = "${var.project_id}.vzdataset.infotype_mapping_local"
        RECOMMENDED_TABLE   = "${var.project_id}.vzdataset.recommended_classification"
      }
    }

    "vz-profiler-job" = {
      image           = "profiler_cloud_run"
      tag             = var.profiler_cloud_run_tag
      max_retries     = 3
      timeout_seconds = 3600
      env_vars = {
        CONFIG_GCS_URI = "gs://vz-datacatalog/data/profiler_config.yaml"
      }
    }

    "vz-trust-score" = {
      image           = "trust_score"
      tag             = var.trust_score_tag
      max_retries     = 3
      timeout_seconds = 3600
      env_vars = {
        TRUST_CONFIG_URI = "gs://vz-datacatalog/data/trust_score_config.json"
      }
    }
  }
}

module "cloudrun_jobs" {
  for_each = local.cloudrun_jobs
  source   = "../../custom_modules/cloudrun_job"

  project_id            = var.project_id
  location              = var.location
  job_name              = each.key
  container_image       = "${local.base_image_uri}/${each.value.image}:${each.value.tag}"
  service_account_email = var.terraform_sa
  
  vpc_connector         = "projects/vz-it-np-exhv-sharedvpc-228116/locations/us-east4/connectors/shared-np-east"
  vpc_egress            = "ALL_TRAFFIC"
  
  max_retries           = each.value.max_retries
  timeout_seconds       = each.value.timeout_seconds
  env_vars              = each.value.env_vars

  labels = {
    purpose = each.key
  }
}
