import csv
import logging
import os
import re
from google.cloud import storage, dlp_v2, bigquery

# ==========================================
# Configuration & Setup
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment Variables injected by Cloud Run
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "my-sdp-config-bucket")
CSV_FILE_NAME = os.environ.get("CSV_FILE_NAME", "sdp_targets.csv")
SDP_PROJECT_ID = os.environ.get("SDP_PROJECT_ID")
DEFAULT_INSPECT_TEMPLATE = os.environ.get("INSPECT_TEMPLATE_NAME", "") # Optional default template fallback

# Results Destination Environment Variables
RESULTS_PROJECT_ID = os.environ.get("RESULTS_PROJECT_ID")
RESULTS_DATASET_ID = os.environ.get("RESULTS_DATASET_ID", "sdp_audit_logs")
RESULTS_TABLE_ID = os.environ.get("RESULTS_TABLE_ID", "dlp_findings")

# Initialize GCP Clients
storage_client = storage.Client()
bq_client = bigquery.Client()
dlp_client = dlp_v2.DlpServiceClient()

# ==========================================
# Core Helper Functions
# ==========================================
def download_csv():
    """Downloads the config CSV from GCS and parses it."""
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(CSV_FILE_NAME)
    reader = csv.DictReader(blob.download_as_text().splitlines())
    return [row for row in reader]

def resolve_tables(row):
    """Resolves projects or datasets into a list of specific BigQuery tables."""
    level = row.get("target_level", "").upper()
    project_id = row.get("project_id")
    dataset_id = row.get("dataset_id")
    table_id = row.get("table_id")
    
    tables_to_scan = []

    if level == "TABLE":
        tables_to_scan.append((project_id, dataset_id, table_id))
    elif level == "DATASET":
        for table in bq_client.list_tables(f"{project_id}.{dataset_id}"):
            tables_to_scan.append((project_id, dataset_id, table.table_id))
    elif level == "PROJECT":
        for dataset in bq_client.list_datasets(project=project_id):
            for table in bq_client.list_tables(dataset.reference):
                tables_to_scan.append((project_id, dataset.dataset_id, table.table_id))
                
    return tables_to_scan

def generate_safe_id(project, dataset, table, job_name):
    """Ensures the job/trigger name is unique and meets GCP regex requirements."""
    raw_id = f"{project}-{dataset}-{table}-{job_name}"
    safe_id = re.sub(r'[^a-zA-Z0-9-]', '-', raw_id).lower()
    return safe_id[:64].strip('-')

def format_template_name(template_input, project_id, location="global"):
    """Formats template ID into a full GCP resource path using the specific location."""
    template_str = template_input.strip() if template_input else ""
    if not template_str:
        template_str = DEFAULT_INSPECT_TEMPLATE

    if not template_str:
        raise ValueError("No inspect_template specified in CSV or environment variable.")

    if template_str.startswith("projects/"):
        return template_str
    else:
        return f"projects/{project_id}/locations/{location}/inspectTemplates/{template_str}"

def create_sdp_action(target_project, dataset_id, table_id, schedule=None, job_name="sdp", inspect_template="", location="global"):
    """Creates either an SDP Job (one-off) or a Job Trigger (scheduled) using an Inspect Template and dynamic Location."""
    # Parent region dynamically created from CSV input
    parent = f"projects/{SDP_PROJECT_ID}/locations/{location}"
    
    # Generate unique action ID and format template resource path with location
    action_id = generate_safe_id(target_project, dataset_id, table_id, job_name)
    template_resource_name = format_template_name(inspect_template, SDP_PROJECT_ID, location)
    
    storage_config = {
        "big_query_options": {
            "table_reference": {
                "project_id": target_project,
                "dataset_id": dataset_id,
                "table_id": table_id,
            }
        }
    }

    actions = [
        {
            "save_findings": {
                "output_config": {
                    "table": {
                        "project_id": RESULTS_PROJECT_ID, 
                        "dataset_id": RESULTS_DATASET_ID, 
                        "table_id": RESULTS_TABLE_ID
                    }
                }
            }
        },
        {
            "publish_findings_to_cloud_data_catalog": {}
        }
    ]

    if not schedule:
        # One-off Inspect Job
        job_config = {
            "inspect_job": {
                "storage_config": storage_config, 
                "inspect_template_name": template_resource_name,
                "actions": actions
            }
        }
        
        response = dlp_client.create_dlp_job(
            request={
                "parent": parent,
                "inspect_job": job_config,
                "job_id": action_id
            }
        )
        logging.info(f"Created Inspect Job: {response.name} in location '{location}' using template '{template_resource_name}'")
    else:
        # Scheduled Job Trigger
        job_trigger = {
            "inspect_job": {
                "storage_config": storage_config, 
                "inspect_template_name": template_resource_name,
                "actions": actions
            },
            "triggers": [{"schedule": {"recurrence_period_duration": {"seconds": 86400}}}],
            "status": dlp_v2.JobTrigger.Status.HEALTHY,
        }
        
        response = dlp_client.create_job_trigger(
            request={
                "parent": parent,
                "job_trigger": job_trigger,
                "trigger_id": action_id
            }
        )
        logging.info(f"Created Job Trigger: {response.name} in location '{location}' using template '{template_resource_name}'")

# ==========================================
# Main Execution Entrypoint
# ==========================================
def main():
    logging.info("Starting SDP Automation Script...")
    try:
        configs = download_csv()
        logging.info(f"Loaded {len(configs)} configurations from GCS.")
        
        for config in configs:
            target_tables = resolve_tables(config)
            schedule = config.get("schedule", "").strip()
            inspect_template = config.get("inspect_template", "").strip()
            
            # Extract location from CSV, default to 'global' if left empty
            location = config.get("location", "").strip()
            if not location:
                location = "global"
            
            job_name = config.get("job_name", "").strip()
            if not job_name:
                job_name = "sdpscan"
            
            for proj, ds, tb in target_tables:
                try:
                    create_sdp_action(proj, ds, tb, schedule, job_name, inspect_template, location)
                except Exception as table_error:
                    logging.error(f"Skipping {proj}.{ds}.{tb} due to error: {table_error}")
                    continue
                
    except Exception as e:
        logging.error(f"Failed to execute SDP automation: {e}")
        raise

if __name__ == "__main__":
    main()