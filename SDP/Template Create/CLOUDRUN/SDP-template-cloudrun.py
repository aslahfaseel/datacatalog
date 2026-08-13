import csv
import logging
import os
from collections import defaultdict
from google.cloud import storage, dlp_v2

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment Variables configured in Cloud Run
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "vz-datacatalog")
CSV_FILE_NAME = os.environ.get("CSV_FILE_NAME", "templates_config.csv")

# ==========================================
# Hardcoded Built-in InfoTypes
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

def download_csv_from_gcs():
    """Downloads CSV content directly from Google Cloud Storage."""
    logging.info(f"Downloading configuration CSV from gs://{GCS_BUCKET_NAME}/{CSV_FILE_NAME}...")
    # Cloud Run automatically handles authentication via its attached Service Account
    storage_client = storage.Client() 
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(CSV_FILE_NAME)
    
    content = blob.download_as_text()
    return content.splitlines()

def create_inspect_templates_from_csv():
    """Reads a CSV for CUSTOM InfoTypes from GCS and merges them with hardcoded BUILTIN types."""
    dlp_client = dlp_v2.DlpServiceClient()
    templates = defaultdict(lambda: {'custom': []})
    
    try:
        csv_lines = download_csv_from_gcs()
        reader = csv.DictReader(csv_lines)
        
        for row in reader:
            project_id = row.get("project_id", "").strip()
            template_id = row.get("template_id", "").strip()
            display_name = row.get("display_name", "").strip()
            description = row.get("description", "").strip()
            region = row.get("region", "global").strip() 
            
            category = row.get("info_type_category", "").strip().upper()
            name = row.get("name", "").strip()
            pattern = row.get("regex_pattern", "").strip()

            if not project_id or not template_id:
                logging.warning("Skipping row: Missing project_id or template_id.")
                continue 

            if category == "CUSTOM" and name and pattern:
                templates[(project_id, template_id, display_name, description, region)]['custom'].append({
                    "info_type": {"name": name},
                    "regex": {"pattern": pattern}
                })
            elif category == "BUILTIN":
                logging.info(f"Ignoring BUILTIN definition from CSV ({name}); using hardcoded list instead.")
                
    except Exception as e:
        logging.error(f"Failed to fetch or parse CSV from GCS: {e}")
        return

    logging.info(f"Found {len(templates)} unique templates to create.")
    formatted_builtins = [{"name": info_type} for info_type in BUILTIN_INFO_TYPES]

    for (project_id, template_id, display_name, description, region), infotypes in templates.items():
        parent = f"projects/{project_id}/locations/{region}"
        
        inspect_config = {
            "info_types": formatted_builtins,
            "custom_info_types": infotypes['custom'],
            "min_likelihood": dlp_v2.Likelihood.LIKELY,
        }

        inspect_template = {
            "display_name": display_name,
            "description": description,
            "inspect_config": inspect_config
        }

        try:
            response = dlp_client.create_inspect_template(
                request={
                    "parent": parent,
                    "inspect_template": inspect_template,
                    "template_id": template_id
                }
            )
            logging.info(f"Success: Created template '{response.name}' in project '{project_id}'")
        except Exception as e:
            logging.error(f"Failed to create template '{template_id}' in project '{project_id}': {e}")

if __name__ == "__main__":
    create_inspect_templates_from_csv()