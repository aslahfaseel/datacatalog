project_id             = "vz-it-np-keiv-dev-dpev-0"
region                 = "us-east4"
location               = "us-east4"
terraform_sa           = "sa-dev-keiv-app-dpev-0@vz-it-np-keiv-dev-dpev-0.iam.gserviceaccount.com"
dataplex_service_agent = "service-594212039830@gcp-sa-dataplex.iam.gserviceaccount.com"
alert_emails = ["your-team@company.com"]

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
