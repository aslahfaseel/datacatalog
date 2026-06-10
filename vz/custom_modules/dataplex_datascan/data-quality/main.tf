# Data Quality Scan Module
# Registry: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_datascan

resource "google_dataplex_datascan" "quality" {
  project      = var.project_id
  location     = var.location
  data_scan_id = var.data_scan_id
  display_name = var.display_name
  description  = var.description
  labels       = var.labels

  data {
    resource = var.source_bq_table
  }

  execution_spec {
    trigger {
      dynamic "on_demand" {
        for_each = var.schedule_cron == null ? [1] : []
        content {}
      }
      dynamic "schedule" {
        for_each = var.schedule_cron != null ? [1] : []
        content {
          cron = var.schedule_cron
        }
      }
    }
  }

  data_quality_spec {
    sampling_percent = var.sampling_percent
    row_filter       = var.row_filter

    dynamic "rules" {
      for_each = var.dq_rules
      content {
        name        = rules.value.name
        description = lookup(rules.value, "description", "")
        dimension   = rules.value.dimension
        threshold   = lookup(rules.value, "threshold", 1.0)
        column      = lookup(rules.value, "column", null)

        dynamic "row_condition_expectation" {
          for_each = lookup(rules.value, "row_condition_sql", null) != null ? [1] : []
          content {
            sql_expression = rules.value.row_condition_sql
          }
        }

        dynamic "sql_assertion" {
          for_each = lookup(rules.value, "sql_assertion", null) != null ? [1] : []
          content {
            sql_statement = rules.value.sql_assertion
          }
        }
      }
    }

    post_scan_actions {
      bigquery_export {
        results_table = var.results_bq_table
      }
    }
  }
}
