data "google_project" "project" {
  project_id = var.project_id
}

resource "google_project_service_identity" "dlp_sa" {
  provider = google-beta
  project  = var.project_id
  service  = "dlp.googleapis.com"
}



resource "google_data_loss_prevention_inspect_template" "bq_inspect" {
  parent       = "projects/${var.project_id}/locations/us"
  display_name = "VZ BQ Sensitive Data Inspection Template"
  description  = "Scans BigQuery tables for common PII and financial sensitive data types"

  inspect_config {
    info_types {
      name = "CREDIT_CARD_NUMBER"
    }
    info_types {
      name = "EMAIL_ADDRESS"
    }
    info_types {
      name = "PHONE_NUMBER"
    }
    info_types {
      name = "US_SOCIAL_SECURITY_NUMBER"
    }
    info_types {
      name = "PERSON_NAME"
    }
    info_types {
      name = "DATE_OF_BIRTH"
    }

    min_likelihood = "LIKELY"
  }
}

resource "google_data_loss_prevention_discovery_config" "bq_discovery" {
  parent   = "projects/${var.project_id}/locations/${var.location}"
  location = var.location
  status   = var.scan_status

  display_name = var.display_name

  inspect_templates = [google_data_loss_prevention_inspect_template.bq_inspect.id]

  targets {
    big_query_target {
      filter {
        other_tables {}
      }

      conditions {
        type_collection = "BIG_QUERY_COLLECTION_ALL_TYPES"
      }

      cadence {
        table_modified_cadence {
          types     = ["TABLE_MODIFIED_TIMESTAMP"]
          frequency = var.scan_frequency
        }
      }
    }
  }

  actions {
    publish_to_dataplex_catalog {}
  }

  actions {
    export_data {
      profile_table {
        project_id = var.project_id
        dataset_id = var.results_dataset_id
        table_id   = var.results_table_id
      }
    }
  }
}