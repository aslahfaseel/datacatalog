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

# Required for Pipeline 2: CREATE OR REPLACE TABLE recommended_classification
resource "google_project_iam_member" "terraform_bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
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

# Required to pull the Cloud Run Docker container from GCR/Artifact Registry
resource "google_project_iam_member" "terraform_artifactregistry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${var.terraform_sa}"
}

# ---------------------------------------------------------
# POLICY TAG ATTACHMENT PERMISSIONS
# ---------------------------------------------------------
# OPTION A (Current / Temporary): broad bigquery.admin role
# TODO: Remove this once security team creates the custom role (Option B)
resource "google_project_iam_member" "terraform_bq_admin" {
  count   = var.custom_policy_tag_stamper_role_id == "" ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${var.terraform_sa}"
}

# OPTION B (Production / Least-Privilege):
# Once security team runs custom_modules/iam_custom_roles and provides
# the custom role ID, this binding replaces the bigquery.admin above.
resource "google_project_iam_member" "terraform_policy_tag_stamper" {
  count   = var.custom_policy_tag_stamper_role_id != "" ? 1 : 0
  project = var.project_id
  role    = var.custom_policy_tag_stamper_role_id
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
