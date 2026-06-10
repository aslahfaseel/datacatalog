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

# ─── MODULE 1: IAM ────────────────────────────────────────────────────────────
# Registry: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_project_iam_member

module "dataplex_iam" {
  source                 = "../../custom_modules/dataplex_iam"
  project_id             = var.project_id
  terraform_sa           = var.terraform_sa
  dataplex_service_agent = var.dataplex_service_agent
}

# ─── MODULE 2: ASPECT TYPES ───────────────────────────────────────────────────
# Registry: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_aspect_type
# Only 1 aspect type: vz-asset-governance
# DQ and Profiling metrics are populated natively by Dataplex scans → no aspect needed for them.

module "aspect_type_asset_governance" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = var.location
  aspect_type_id = "vz-asset-governance"
  display_name   = "VZ Asset Governance"
  description    = "Governance metadata: owner, domain, and lifecycle stage of the data asset"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "vz-asset-governance"
    type         = "record"
    recordFields = [
      {
        name        = "owner"
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
          { name = "customer",   index = 1 },
          { name = "finance",    index = 2 },
          { name = "network",    index = 3 },
          { name = "operations", index = 4 },
          { name = "sales",      index = 5 },
          { name = "risk",       index = 6 }
        ]
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

# ─── MODULE 3: DATA PROFILING SCAN ────────────────────────────────────────────
# Registry: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_datascan
# Results exported to BQ and auto-surfaced as "Data Profile" tab in Knowledge Catalog entry.

module "profiling_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan/data-profiling"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "vz-raw-profiling-daily"
  display_name     = "VZ Raw - Daily Profiling"
  description      = "Automated daily profiling scan for vzdataset.raw"
  labels           = merge(local.common_labels, { scan_type = "profiling" })
  source_bq_table  = "${local.bq_prefix}/datasets/vzdataset/tables/raw"
  results_bq_table = local.profile_results_table
  schedule_cron    = "0 0 * * *"
  sampling_percent = 100.0
  depends_on       = [module.dataplex_iam]
}

# ─── MODULE 4: DATA QUALITY SCAN ─────────────────────────────────────────────
# Registry: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_datascan
# Results exported to BQ and auto-surfaced as "Data Quality" tab in Knowledge Catalog entry.

module "dq_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan/data-quality"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "vz-raw-dq-daily"
  display_name     = "VZ Raw - Daily Data Quality"
  description      = "Automated daily DQ scan for vzdataset.raw"
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
