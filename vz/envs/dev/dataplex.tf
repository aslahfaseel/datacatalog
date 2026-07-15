locals {
  bq_prefix             = "//bigquery.googleapis.com/projects/${var.project_id}"
  dq_results_table      = "${local.bq_prefix}/datasets/gcp_governance_tbls/tables/data_quality_results"
  profile_results_table = "${local.bq_prefix}/datasets/gcp_governance_tbls/tables/data_profiling_results"
  common_labels = {
    project     = "vz"
    environment = "dev"
    managed_by  = "terraform"
  }
}

#module "dataplex_iam" {
  #source                 = "../../custom_modules/dataplex_iam"
  #project_id             = var.project_id
  #terraform_sa           = var.terraform_sa
  #dataplex_service_agent = var.dataplex_service_agent
#}

module "aspect_type_asset_governance" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = "us"
  aspect_type_id = "data-governance"
  display_name   = "Data Governance"
  description    = "Governance metadata: owner, domain, and lifecycle stage of the data asset"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "data-governance"
    type         = "record"
    recordFields = [
      {
        name        = "data_owner"
        type        = "string"
        index       = 1
        annotations = { displayName = "Data Owner", description = " Business / Functional lead that manages the data" }
        constraints = { required = false }
      },
      
      {
        name        = "data_domain"
        type        = "string"
        index       = 2
        annotations = { displayName = "Data Domain", description = " Sample values = Accessory Sales, Accounts Payable & Accounts Receivable"}       
        constraints = { required = false }
      },

      {
        name        = "data_domain_description"
        type        = "text"
        index       = 2
        annotations = { displayName = "Data domain description", description = "description"}       
        constraints = { required = false }
      },

      {
        name        = "data_lifecycle"
        type        = "enum"
        index       = 3
        annotations = { displayName = "Data Lifecycle", description = "Indication of the data layer for the attached object" }
        enumValues = [
          { name = "Landing Zone Bronze Layer", index = 1 },
          { name = "Processing Zone Silver Layer", index = 2 },
          { name = "Curated Zone Gold Layer", index = 3 }
        ]
        constraints = { required = false }
      }
    ]
  })
}

module "aspect_type_data_trustability" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = "vz-it-np-keiv-dev-dpev-0"
  location       = "us"
  aspect_type_id = "data-trustability"
  display_name   = "Data Trustability"
  description    = "Aspect type for overall tracking of automated and manual data trust levels"
  labels         = local.common_labels

  metadata_template = jsonencode({
    name         = "data-trustability"
    type         = "record"
    recordFields = [
      {
        name        = "trust_score"
        type        = "enum"
        index       = 1
        annotations = {
          displayName = "Trust Score"
          description = "The overall trust tier based on domain evaluation rule outcomes"
        }
        constraints = { required = false }
        enumValues = [
          { name = "high",    index = 1 },
          { name = "medium",  index = 2 },
          { name = "low",     index = 3 },
          { name = "unknown", index = 4 }
        ]
      },
      {
        name        = "last_evaluated"
        type        = "datetime"
        index       = 2
        annotations = {
          displayName = "Last Evaluated"
          description = "The exact timestamp when the data quality scan was executed."
        }
        constraints = { required = false }
      }
    ]
  })
}

module "profiling_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan/data-profiling"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "${var.project_id}-coetables-tspot-vzt-fact-oneex-dp-scan"
  display_name     = "${var.project_id}-tspot_vzt_fact_oneex-dataprofile-scan"
  description      = "Automated daily profiling scan for vzdataset.raw"
  labels           = merge(local.common_labels, { scan_type = "profiling" })
  source_bq_table  = "${local.bq_prefix}/datasets/coe_tbls/tables/tspot_vzt_fact_oneex"
  results_bq_table = local.profile_results_table
  schedule_cron    = "0 0 * * *"
  sampling_percent = 100.0
  #depends_on       = [module.dataplex_iam]
}

module "dq_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan/data-quality"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "${var.project_id}-coetables-tspot-vzt-fact-oneex-dq-scan"
  display_name     = "${var.project_id}-coetables-tspot_vzt_fact_oneex-dataquality-scan"
  description      = "Automated daily DQ scan for vzdataset.raw"
  labels           = merge(local.common_labels, { scan_type = "dq" })
  source_bq_table  = "${local.bq_prefix}/datasets/coe_tbls/tables/tspot_vzt_fact_oneex"
  results_bq_table = local.dq_results_table
  schedule_cron    = "0 6 * * *"
  sampling_percent = 100.0
  dq_rules = [
    {
      name              = "id-not-null"
      dimension         = "COMPLETENESS"
      threshold         = 1.0
      column            = "date_id"
      row_condition_sql = "date_id IS NOT NULL"
    }
  ]
  #depends_on = [module.dataplex_iam]
}

data "google_client_config" "default" {}

data "http" "profile_scan_details" {
  for_each = var.dq_profile_scans
  url      = "https://dataplex.googleapis.com/v1/projects/${each.value.project_id}/locations/${each.value.region}/dataScans/${each.value.existing_profile_scan_id}"
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
  for_each     = var.dq_profile_scans
  project      = each.value.project_id
  location     = each.value.region
  data_scan_id = each.value.existing_profile_scan_id
}

resource "google_dataplex_datascan" "dq_from_profile" {
  for_each     = var.dq_profile_scans
  project      = each.value.project_id
  location     = each.value.region
  data_scan_id = each.value.new_dq_scan_id
  display_name = "DQ (Profile Recommendations) - ${each.value.existing_profile_scan_id}"
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

  #depends_on = [module.dataplex_iam]
}

#module "sensitive_data_protection" {
  #source = "../../custom_modules/dataplex_sdp"

  # ---------------------------------------------------------
  # DETAILS YOU MUST UPDATE:
  # ---------------------------------------------------------
  
  # 1. Update this to your actual GCP Project ID where BigQuery lives
  #project_id = var.project_id
  
  # 2. DLP Discovery Configs must be in the multi-region 'us' location � do not change this
  #location   = "us"
  
  # 3. (Optional) Customize the sensitive data types you want to find.
  # If you don't include this block, it will use the default list from variables.tf
  #info_types = [
    #"EMAIL_ADDRESS",
    #"CREDIT_CARD_NUMBER",
    #"US_SOCIAL_SECURITY_NUMBER",
    #"PERSON_NAME",
    #"PHONE_NUMBER",
    #"GCP_CREDENTIALS"
  #]
#}
