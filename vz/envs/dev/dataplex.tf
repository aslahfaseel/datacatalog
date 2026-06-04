locals {
  bq_prefix             = "//bigquery.googleapis.com/projects/${var.project_id}"
  dq_results_table      = "${local.bq_prefix}/datasets/vzdataset/tables/dq_results"
  profile_results_table = "${local.bq_prefix}/datasets/vzdataset/tables/profiling_results"
  common_labels = {
    project     = "vz"
    environment = "dev"
    managed_by  = "terraform"
  }
}

module "dataplex_iam" {
  source                 = "../../custom_modules/dataplex_iam"
  project_id             = var.project_id
  terraform_sa           = var.terraform_sa
  dataplex_service_agent = var.dataplex_service_agent
}

module "aspect_type_business_metadata" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = var.location
  aspect_type_id = "vz-business-metadata"
  display_name   = "VZ Business Metadata"
  description    = "Business metadata for vz tables"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "vz-business-metadata"
    type         = "record"
    recordFields = [
      {
        name        = "data_owner"
        type        = "string"
        index       = 1
        annotations = { displayName = "Data Owner" }
        constraints = { required = true }
      },
      {
        name        = "domain"
        type        = "enum"
        index       = 2
        annotations = { displayName = "Business Domain" }
        enumValues = [
          { name = "sales",      index = 1 },
          { name = "network",    index = 2 },
          { name = "customer",   index = 3 },
          { name = "finance",    index = 4 },
          { name = "operations", index = 5 }
        ]
        constraints = { required = true }
      }
    ]
  })

  depends_on = [module.dataplex_iam]
}

module "aspect_type_data_classification" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = var.location
  aspect_type_id = "vz-data-classification"
  display_name   = "VZ Data Classification"
  description    = "PII and sensitivity classification"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "vz-data-classification"
    type         = "record"
    recordFields = [
      {
        name        = "pii_flag"
        type        = "string"
        index       = 1
        annotations = { displayName = "Contains PII (true/false)" }
        constraints = { required = true }
      },
      {
        name        = "sensitivity_level"
        type        = "enum"
        index       = 2
        annotations = { displayName = "Sensitivity Level" }
        enumValues = [
          { name = "public",           index = 1 },
          { name = "internal",         index = 2 },
          { name = "confidential",     index = 3 },
          { name = "highly_sensitive", index = 4 }
        ]
        constraints = { required = true }
      }
    ]
  })

  depends_on = [module.dataplex_iam]
}

module "profiling_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "vz-raw-profiling-daily"
  display_name     = "VZ Raw - Daily Profiling"
  scan_type        = "profiling"
  labels           = merge(local.common_labels, { scan_type = "profiling" })
  source_bq_table  = "${local.bq_prefix}/datasets/vzdataset/tables/raw"
  results_bq_table = local.profile_results_table
  schedule_cron    = "0 0 * * *"
  sampling_percent = 100.0
  depends_on       = [module.dataplex_iam]
}

module "dq_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "vz-raw-dq-daily"
  display_name     = "VZ Raw - Daily Data Quality"
  scan_type        = "quality"
  labels           = merge(local.common_labels, { scan_type = "dq" })
  source_bq_table  = "${local.bq_prefix}/datasets/vzdataset/tables/raw"
  results_bq_table = local.dq_results_table
  schedule_cron    = "0 6 * * *"
  sampling_percent = 100.0
  dq_rules = [
    {
      name              = "id-not-null"
      dimension         = "COMPLETENESS"
      threshold         = 1.0
      column            = "id"
      row_condition_sql = "id IS NOT NULL"
    }
  ]
  depends_on = [module.dataplex_iam]
}
