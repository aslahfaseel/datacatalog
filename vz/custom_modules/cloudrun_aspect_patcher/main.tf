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

# NOTE: Cloud Scheduler is NOT managed here because cloudscheduler.admin
# permission is not available. To trigger this job manually, use:
#   gcloud run jobs execute vz-aspect-patcher --region=us-central1
# Or trigger on demand from the Cloud Run Jobs page in the GCP Console.

# NOTE: GCS bucket IAM for 'vz-datacatalog' bucket must be granted manually
# by the GCS bucket owner team. Ask them to run:
#   gcloud storage buckets add-iam-policy-binding gs://vz-datacatalog \
#     --member="serviceAccount:vz-datacatalog@dmgcp-del-181.iam.gserviceaccount.com" \
#     --role="roles/storage.objectViewer"

resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = local.job_sa_member
}
