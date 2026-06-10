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

# ─── ASPECT TYPES ─────────────────────────────────────────────────────────────

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

module "aspect_type_asset_governance" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = var.location
  aspect_type_id = "vz-asset-governance"
  display_name   = "VZ Asset Governance"
  description    = "Governance metadata: domain, owner, and lifecycle stage of the asset"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "vz-asset-governance"
    type         = "record"
    recordFields = [
      {
        name        = "domain"
        type        = "enum"
        index       = 1
        annotations = { displayName = "Data Domain" }
        enumValues = [
          { name = "customer",    index = 1 },
          { name = "finance",     index = 2 },
          { name = "network",     index = 3 },
          { name = "operations",  index = 4 },
          { name = "sales",       index = 5 },
          { name = "risk",        index = 6 }
        ]
        constraints = { required = true }
      },
      {
        name        = "owner"
        type        = "string"
        index       = 2
        annotations = { displayName = "Data Owner" }
        constraints = { required = true }
      },
      {
        name        = "lifecycle"
        type        = "enum"
        index       = 3
        annotations = { displayName = "Data Lifecycle Stage" }
        enumValues = [
          { name = "active",       index = 1 },
          { name = "deprecated",   index = 2 },
          { name = "archived",     index = 3 },
          { name = "under_review", index = 4 }
        ]
        constraints = { required = true }
      }
    ]
  })

  depends_on = [module.dataplex_iam]
}

module "aspect_type_table_profiling_metrics" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = var.location
  aspect_type_id = "vz-table-profiling-metrics"
  display_name   = "VZ Table Profiling Metrics"
  description    = "Auto-populated profiling statistics: row count, table size, and last profiled timestamp"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "vz-table-profiling-metrics"
    type         = "record"
    recordFields = [
      {
        name        = "total_row_count"
        type        = "string"
        index       = 1
        annotations = { displayName = "Total Row Count" }
        constraints = { required = false }
      },
      {
        name        = "total_size_of_table"
        type        = "string"
        index       = 2
        annotations = { displayName = "Total Size of Table (MB)" }
        constraints = { required = false }
      },
      {
        name        = "last_profile_timestamp"
        type        = "string"
        index       = 3
        annotations = { displayName = "Last Profile Run Timestamp (UTC)" }
        constraints = { required = false }
      }
    ]
  })

  depends_on = [module.dataplex_iam]
}

module "aspect_type_table_quality_metrics" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = var.location
  aspect_type_id = "vz-table-quality-metrics"
  display_name   = "VZ Table Quality Metrics"
  description    = "Auto-populated DQ scan results: rules evaluated, failed, and critical failure status"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "vz-table-quality-metrics"
    type         = "record"
    recordFields = [
      {
        name        = "scan_status"
        type        = "enum"
        index       = 1
        annotations = { displayName = "Last Scan Status" }
        enumValues = [
          { name = "passed",  index = 1 },
          { name = "failed",  index = 2 },
          { name = "pending", index = 3 }
        ]
        constraints = { required = false }
      },
      {
        name        = "rules_evaluated_count"
        type        = "string"
        index       = 2
        annotations = { displayName = "Rules Evaluated Count" }
        constraints = { required = false }
      },
      {
        name        = "rules_failed_count"
        type        = "string"
        index       = 3
        annotations = { displayName = "Rules Failed Count" }
        constraints = { required = false }
      },
      {
        name        = "critical_failure_flag"
        type        = "enum"
        index       = 4
        annotations = { displayName = "Critical Failure Flag" }
        enumValues = [
          { name = "true",  index = 1 },
          { name = "false", index = 2 }
        ]
        constraints = { required = false }
      }
    ]
  })

  depends_on = [module.dataplex_iam]
}

module "aspect_type_asset_reliability_trust" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = var.location
  aspect_type_id = "vz-asset-reliability-trust"
  display_name   = "VZ Asset Reliability & Trust"
  description    = "Trustability score inferred from domain DQ thresholds and scan results"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "vz-asset-reliability-trust"
    type         = "record"
    recordFields = [
      {
        name        = "trust_score_rating"
        type        = "enum"
        index       = 1
        annotations = { displayName = "Trust Score Rating" }
        enumValues = [
          { name = "high",     index = 1 },
          { name = "medium",   index = 2 },
          { name = "low",      index = 3 },
          { name = "critical", index = 4 }
        ]
        constraints = { required = false }
      }
    ]
  })

  depends_on = [module.dataplex_iam]
}

# ─── DATA SCANS ────────────────────────────────────────────────────────────────

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
