locals {
  job_sa_member = "serviceAccount:${var.service_account_email}"
}

resource "google_cloud_run_v2_job" "aspect_patcher" {
  name     = var.job_name
  location = var.location
  project  = var.project_id
  labels   = var.labels

  template {
    labels      = var.labels
    parallelism = 1
    task_count  = 1

    template {
      service_account = var.service_account_email
      max_retries     = var.max_retries
      timeout         = "${var.timeout_seconds}s"

      containers {
        image = var.container_image

        env {
          name  = "GCS_BUCKET_NAME"
          value = var.gcs_bucket_name
        }
        env {
          name  = "GCS_CSV_PATH"
          value = var.gcs_csv_path
        }
        env {
          name  = "DATAPLEX_PROJECT_ID"
          value = var.dataplex_project_id
        }
        env {
          name  = "DATAPLEX_LOCATION"
          value = var.location
        }

        # Pipeline 2: Data Classification (manager's code)
        env {
          name  = "GOVERNANCE_PROJECT"
          value = var.governance_project
        }
        env {
          name  = "CURATED_PROJECT"
          value = var.curated_project
        }
        env {
          name  = "DLP_RESULTS_TABLE"
          value = var.dlp_results_table
        }
        env {
          name  = "MAPPING_TABLE"
          value = var.mapping_table
        }
        env {
          name  = "RECOMMENDED_TABLE"
          value = var.recommended_table
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }
}

