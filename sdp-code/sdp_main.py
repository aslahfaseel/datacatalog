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

# Results Destination Environment Variables
RESULTS_PROJECT_ID = os.environ.get("RESULTS_PROJECT_ID")
RESULTS_DATASET_ID = os.environ.get("RESULTS_DATASET_ID", "sdp_audit_logs")
RESULTS_TABLE_ID = os.environ.get("RESULTS_TABLE_ID", "dlp_findings")

# Initialize GCP Clients
storage_client = storage.Client()
bq_client = bigquery.Client()
dlp_client = dlp_v2.DlpServiceClient()

# ==========================================
# 1. Custom Regex InfoTypes
# ==========================================
CUSTOM_REGEX_DEFINITIONS = [
    {"name": "CUSTOM_ALPHANUM_SYMBOLS", "pattern": r"^(?:[A-Za-z0-9_\-/*+ .]+|\s*)$"},
    {"name": "CUSTOM_ANY_TEXT_MULTILINE", "pattern": r"(?s)^[\s\S]+$"},
    {"name": "CUSTOM_IP_ADDRESS", "pattern": r"\b(?:(?:\d{1,3}\.){3}\d{1,3}|(?:[a-fA-F0-9]{1,4}:){1,7}(?::|[a-fA-F0-9]{1,4})?|(?:::[a-fA-F0-9]{1,4}))\b"},
    {"name": "CUSTOM_IDENTIFIER_SHORT", "pattern": r"^([A-Za-z0-9-+=*@|. _/]{1,50}|\s*)$"},
    {"name": "CUSTOM_ALPHANUM_DASH_AMP", "pattern": r"^([A-Za-z0-9\-*&| _]+|\s*)$"},
    {"name": "CUSTOM_HEX_OR_DIGITS", "pattern": r"^(\d{4,6}|[A-Fa-f0-9]{16}|[A-Fa-f0-9]{32})$"},
    {"name": "CUSTOM_ALPHANUM_BASIC", "pattern": r"^([A-Za-z0-9*]+|\s*)$"},
    {"name": "CUSTOM_PRINTABLE_TEXT", "pattern": r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]{1,500}$"},
    {"name": "CUSTOM_PHONE_FORMAT", "pattern": r"^(\+?\d{1,3})?[\s./-]?\(?\d{1,4}\)?[\s./-]?\d{1,4}[\s./-]?\d{1,9}(.*)?$"},
    {"name": "CUSTOM_CASE_INSENSITIVE_HASH", "pattern": r"(?i)^[a-z0-9#]{1,10}$"},
    {"name": "CUSTOM_CASE_INSENSITIVE_ALPHANUM", "pattern": r"(?i)^[a-z0-9]{1,10}$"},
]

# ==========================================
# 2. Built-in InfoTypes
# ==========================================
BUILTIN_INFO_TYPES = [
    "CREDIT_CARD_NUMBER", "CVV_NUMBER", "PASSWORD", "CREDIT_CARD_TRACK_NUMBER",
    "FINANCIAL_ACCOUNT_NUMBER", "US_SOCIAL_SECURITY_NUMBER", "DRIVERS_LICENSE_NUMBER",
    "IMMIGRATION_STATUS", "US_INDIVIDUAL_TAXPAYER_IDENTIFICATION_NUMBER",
    "DOD_ID_NUMBER", "PASSPORT", "MEDICAL_DATA", "GOVERNMENT_ID",
    "US_EMPLOYER_IDENTIFICATION_NUMBER", "GENERIC_ID", "FEMALE_NAME",
    "DATE_OF_BIRTH", "PHONE_NUMBER", "SECURITY_DATA", "DEMOGRAPHIC_DATA",
    "EMAIL_ADDRESS", "LOCATION", "ADVERTISING_ID", "URL", "IP_ADDRESS",
    "IMEI_HARDWARE_ID", "MAC_ADDRESS", "PERSON_NAME", "DOCUMENT_TYPE/R&D/SOURCE_CODE",
    "DOCUMENT_TYPE/LEGAL/LAW", "DOCUMENT_TYPE/R&D/PATENT", "TECHNICAL_ID",
    "DATE", "CREDIT_CARD_DATA", "STREET_ADDRESS", "LOCATION_COORDINATES",
    "CRIME_STATUS", "OBJECT_TYPE/PERSON/PHOTO_ID_CARD", "POLITICAL_TERM",
    "RELIGIOUS_TERM", "SEXUAL_ORIENTATION", "TRADE_UNION", "ETHNIC_GROUP",
    "AGE", "EMPLOYMENT_STATUS", "VEHICLE_IDENTIFICATION_NUMBER"
]

# ==========================================
# Core Functions
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

    try:
        if level == "TABLE":
            tables_to_scan.append((project_id, dataset_id, table_id))
        elif level == "DATASET":
            for table in bq_client.list_tables(f"{project_id}.{dataset_id}"):
                tables_to_scan.append((project_id, dataset_id, table.table_id))
        elif level == "PROJECT":
            for dataset in bq_client.list_datasets(project=project_id):
                for table in bq_client.list_tables(dataset.reference):
                    tables_to_scan.append((project_id, dataset.dataset_id, table.table_id))
    except Exception as e:
        logging.warning(f"Error fetching BigQuery targets for {project_id}:{dataset_id}: {e}")
                    
    return tables_to_scan

def generate_safe_id(project, dataset, table, job_name):
    """Ensures the job/trigger name is unique and meets GCP regex requirements."""
    # Prefix the ID with project, dataset, and table
    raw_id = f"{project}-{dataset}-{table}-{job_name}"
    
    # Replace anything that isn't a letter or number with a hyphen
    safe_id = re.sub(r'[^a-zA-Z0-9-]', '-', raw_id).lower()
    
    # Truncate to 64 chars max (GCP limit) and remove trailing hyphens
    return safe_id[:64].strip('-')

def create_sdp_action(target_project, dataset_id, table_id, schedule=None, job_name="sdp"):
    """Creates either an SDP Job (one-off) or a Job Trigger (scheduled) with Actions."""
    location = os.environ.get("SDP_LOCATION", "us-central1")
    parent = f"projects/{SDP_PROJECT_ID}/locations/{location}"
    
    # Generate the ID with project, dataset, and table prefix
    action_id = generate_safe_id(target_project, dataset_id, table_id, job_name)
    
    storage_config = {
        "big_query_options": {
            "table_reference": {
                "project_id": target_project,
                "dataset_id": dataset_id,
                "table_id": table_id,
            }
        }
    }

    # Prepare standard Built-in InfoTypes
    formatted_builtins = [{"name": info_type} for info_type in BUILTIN_INFO_TYPES if "/" not in info_type]

    # Prepare Custom Regex InfoTypes
    formatted_customs = [
        {
            "info_type": {"name": custom["name"]},
            "regex": {"pattern": custom["pattern"]}
        }
        for custom in CUSTOM_REGEX_DEFINITIONS
    ]

    # Merge into the inspect_config payload
    inspect_config = {
        "info_types": formatted_builtins,
        "custom_info_types": formatted_customs,
        "min_likelihood": dlp_v2.Likelihood.LIKELY,
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
        inspect_job_config = {
            "storage_config": storage_config, 
            "inspect_config": inspect_config, 
            "actions": actions
        }
        
        response = dlp_client.create_dlp_job(
            request={
                "parent": parent,
                "inspect_job": inspect_job_config,
                "job_id": action_id
            }
        )
        logging.info(f"Created Inspect Job: {response.name}")
    else:
        job_trigger = {
            "inspect_job": {
                "storage_config": storage_config, 
                "inspect_config": inspect_config, 
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
        logging.info(f"Created Job Trigger: {response.name}")

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
            
            job_name = config.get("job_name", "").strip()
            if not job_name:
                job_name = "sdpscan"
            
            for proj, ds, tb in target_tables:
                try:
                    create_sdp_action(proj, ds, tb, schedule, job_name)
                except Exception as table_error:
                    logging.error(f"Skipping {proj}.{ds}.{tb} due to error: {table_error}")
                    continue
                
    except Exception as e:
        logging.error(f"Failed to execute SDP automation: {e}")
        raise

if __name__ == "__main__":
    main()