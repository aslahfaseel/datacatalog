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

}


# Dynamically fetch the CSV from GCS so Data Stewards can manage it without touching Git
data "google_storage_bucket_object_content" "tables_csv" {
  name   = "data/tables_to_scan.csv"
  bucket = "vz-datacatalog"
}

locals {
  rule_library = {
    "id-not-null" = {
      name              = "id-not-null"
      dimension         = "COMPLETENESS"
      column            = "id"
      row_condition_sql = "id IS NOT NULL"
    }
    "raw-table-has-data" = {
      name                = "raw-table-has-data"
      dimension           = "COMPLETENESS"
      table_condition_sql = "COUNT(*) > 0"
    }
  }

  # Read the CSV from GCS
  tables_raw = csvdecode(data.google_storage_bucket_object_content.tables_csv.content)

  tables_to_scan = {
    for row in local.tables_raw :
    row.table_key => {
      dataset  = row.dataset
      table    = row.table
      # Split by semi-colon and map to full rules, ignore gracefully if empty
      dq_rules = row.dq_rules == "" ? [] : [
        for rule_name in split(";", row.dq_rules) : local.rule_library[trimspace(rule_name)]
      ]
    }
  }
}

module "profiling_scan" {
  for_each         = local.tables_to_scan
  source           = "../../custom_modules/dataplex_datascan/data-profiling"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "vz-${replace(each.key, "_", "-")}-profiling-daily"
  display_name     = "VZ ${title(replace(each.key, "_", " "))} - Daily Profiling"
  description      = "Automated daily profiling scan for ${each.value.dataset}.${each.value.table}"
  labels           = merge(local.common_labels, { scan_type = "profiling" })
  source_bq_table  = "${local.bq_prefix}/datasets/${each.value.dataset}/tables/${each.value.table}"
  results_bq_table = local.profile_results_table
  schedule_cron    = "0 0 * * *"
  sampling_percent = 100.0
}

module "dq_scan" {
  for_each         = local.tables_to_scan
  source           = "../../custom_modules/dataplex_datascan/data-quality"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "vz-${replace(each.key, "_", "-")}-dq-daily"
  display_name     = "VZ ${title(replace(each.key, "_", " "))} - Daily Data Quality"
  description      = "Automated daily DQ scan for ${each.value.dataset}.${each.value.table}"
  labels           = merge(local.common_labels, { scan_type = "dq" })
  source_bq_table  = "${local.bq_prefix}/datasets/${each.value.dataset}/tables/${each.value.table}"
  results_bq_table = local.dq_results_table
  schedule_cron    = "0 6 * * *"
  sampling_percent = 100.0
  dq_rules         = each.value.dq_rules
}


data "google_client_config" "default" {}

data "http" "profile_scan_details" {
  for_each = var.dq_profile_scans

  url = "https://dataplex.googleapis.com/v1/projects/${each.value.project_id}/locations/${each.value.region}/dataScans/${each.value.existing_profile_scan_id}"

  request_headers = {
    Authorization = "Bearer ${data.google_client_config.default.access_token}"
    Accept        = "application/json"
  }
}

locals {
  profile_target_resources = {
    for key, response in data.http.profile_scan_details :
    key => jsondecode(response.response_body).data.resource
  }
}

data "google_dataplex_data_quality_rules" "recommendations" {
  for_each = var.dq_profile_scans

  project      = each.value.project_id
  location     = each.value.region
  data_scan_id = each.value.existing_profile_scan_id
}

resource "google_dataplex_datascan" "dq_from_profile" {
  for_each = var.dq_profile_scans

  project      = each.value.project_id
  location     = each.value.region
  data_scan_id = each.value.new_dq_scan_id
  display_name = "DQ (Profile Recommendations) — ${each.value.existing_profile_scan_id}"
  labels       = merge(local.common_labels, { scan_type = "dq-profile-based" })

  data {
    resource = local.profile_target_resources[each.key]
  }

  execution_spec {
    trigger {
      schedule {
        cron = "0 6 * * *"
      }
    }
  }

  data_quality_spec {
    catalog_publishing_enabled = true

    dynamic "rules" {
      for_each = data.google_dataplex_data_quality_rules.recommendations[each.key].rules
      content {
        column      = rules.value.column
        dimension   = rules.value.dimension
        threshold   = rules.value.threshold
        ignore_null = rules.value.ignore_null
        name        = rules.value.name
        description = rules.value.description

        dynamic "non_null_expectation" {
          for_each = rules.value.non_null_expectation
          content {}
        }
        dynamic "uniqueness_expectation" {
          for_each = rules.value.uniqueness_expectation
          content {}
        }
        dynamic "range_expectation" {
          for_each = rules.value.range_expectation
          content {
            min_value          = range_expectation.value.min_value
            max_value          = range_expectation.value.max_value
            strict_min_enabled = range_expectation.value.strict_min_enabled
            strict_max_enabled = range_expectation.value.strict_max_enabled
          }
        }
        dynamic "regex_expectation" {
          for_each = rules.value.regex_expectation
          content {
            regex = regex_expectation.value.regex
          }
        }
        dynamic "set_expectation" {
          for_each = rules.value.set_expectation
          content {
            values = set_expectation.value.values
          }
        }
        dynamic "statistic_range_expectation" {
          for_each = rules.value.statistic_range_expectation
          content {
            statistic          = statistic_range_expectation.value.statistic
            min_value          = statistic_range_expectation.value.min_value
            max_value          = statistic_range_expectation.value.max_value
            strict_min_enabled = statistic_range_expectation.value.strict_min_enabled
            strict_max_enabled = statistic_range_expectation.value.strict_max_enabled
          }
        }
        dynamic "row_condition_expectation" {
          for_each = rules.value.row_condition_expectation
          content {
            sql_expression = row_condition_expectation.value.sql_expression
          }
        }
        dynamic "table_condition_expectation" {
          for_each = rules.value.table_condition_expectation
          content {
            sql_expression = table_condition_expectation.value.sql_expression
          }
        }
        dynamic "sql_assertion" {
          for_each = rules.value.sql_assertion
          content {
            sql_statement = sql_assertion.value.sql_statement
          }
        }
      }
    }

    post_scan_actions {
      bigquery_export {
        results_table = local.dq_results_table
      }
    }
  }

}

module "sensitive_data_protection" {
  source = "../../custom_modules/dataplex_sdp"

  project_id = var.project_id
  
  # 2. DLP Discovery Configs must be in the multi-region 'us' location — do not change this
  location   = "us"
  
  # 3. (Optional) Customize the sensitive data types you want to find.
  # If you don't include this block, it will use the default list from variables.tf
  info_types = [
    "EMAIL_ADDRESS",
    "CREDIT_CARD_NUMBER",
    "US_SOCIAL_SECURITY_NUMBER",
    "PERSON_NAME",
    "PHONE_NUMBER",
    "GCP_CREDENTIALS"
  ]
}
