# =============================================================================
# ▼▼▼ CLIENT ENVIRONMENT — UPDATE THESE VALUES ▼▼▼
# =============================================================================

project_id             = "vz-it-np-keiv-dev-dpev-0"
region                 = "us-east4"
location               = "us-east4"
terraform_sa           = "sa-dev-keiv-app-dpev-0@vz-it-np-keiv-dev-dpev-0.iam.gserviceaccount.com"
dataplex_service_agent = "service-594212039830@gcp-sa-dataplex.iam.gserviceaccount.com"
alert_emails           = ["your-team@company.com"]

# GCS bucket holding the 3 CSV config files
gcs_bucket_name = "vz-datacatalog"

# Cloud Run image tags (updated per deployment)
bulk_aspect_apply_tag  = "latest"
profiler_cloud_run_tag = "latest"
trust_score_tag        = "latest"
