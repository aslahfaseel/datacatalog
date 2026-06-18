resource "google_project_iam_member" "terraform_dataplex_editor" {
  project = var.project_id
  role    = "roles/dataplex.editor"
  member  = "serviceAccount:${var.terraform_sa}"
}

resource "google_project_iam_member" "terraform_catalog_editor" {
  project = var.project_id
  role    = "roles/dataplex.catalogEditor"
  member  = "serviceAccount:${var.terraform_sa}"
}

resource "google_project_iam_member" "terraform_bq_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${var.terraform_sa}"
}

resource "google_project_iam_member" "terraform_bq_metadata_viewer" {
  project = var.project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:${var.terraform_sa}"
}

resource "google_project_iam_member" "terraform_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${var.terraform_sa}"
}

# Required for Cloud Run Job creation
resource "google_project_iam_member" "terraform_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${var.terraform_sa}"
}

# Required for Cloud Scheduler job creation
resource "google_project_iam_member" "terraform_scheduler_admin" {
  project = var.project_id
  role    = "roles/cloudscheduler.admin"
  member  = "serviceAccount:${var.terraform_sa}"
}

resource "google_project_iam_member" "dataplex_bq_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${var.dataplex_service_agent}"
}

resource "google_project_iam_member" "dataplex_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.dataplex_service_agent}"
}

resource "google_project_iam_member" "dataplex_bq_metadata_viewer" {
  project = var.project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:${var.dataplex_service_agent}"
}
