# Data Profiling Scan Module
# Registry: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_datascan

resource "google_dataplex_datascan" "profiling" {
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

  data_profile_spec {
    sampling_percent = var.sampling_percent
    row_filter       = var.row_filter

    post_scan_actions {
      bigquery_export {
        results_table = var.results_bq_table
      }
    }
  }
}
