project_id  = "dmgcp-del-181"
region      = "us-central1"
location    = "us-central1"
terraform_sa = "vz-datacatalog@dmgcp-del-181.iam.gserviceaccount.com"
dataplex_service_agent = "service-308053638624@gcp-sa-dataplex.iam.gserviceaccount.com"
alert_emails = ["your-team@company.com"]

# Profile-based DQ scans — add one entry per table to scale up to 50 tables
# existing_profile_scan_id = profiling scan that has run at least once and generated recommendations
# new_dq_scan_id           = new DQ scan Terraform will create from those recommendations
dq_profile_scans = {
  raw = {
    project_id               = "dmgcp-del-181"
    region                   = "us-central1"
    existing_profile_scan_id = "vz-raw-profiling-daily"
    new_dq_scan_id           = "vz-raw-dq-profile-based"
  }
  # Add more tables here, e.g.:
  # raw_customer = {
  #   project_id               = "dmgcp-del-181"
  #   region                   = "us-central1"
  #   existing_profile_scan_id = "vz-raw-customer-profiling-daily"
  #   new_dq_scan_id           = "vz-raw-customer-dq-profile-based"
  # }
}
