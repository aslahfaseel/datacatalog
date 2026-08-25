import csv
import logging
import os
import sys
from collections import defaultdict
from google.auth import default, impersonated_credentials
from google.cloud import storage, dlp_v2

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment Variables
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "vz-datacatalog")
CSV_FILE_NAME = os.environ.get("CSV_FILE_NAME", "templates_config.csv")
TARGET_SERVICE_ACCOUNT = os.environ.get(
    "TARGET_SERVICE_ACCOUNT",
    "vz-datacatalog@dmgcp-del-181.iam.gserviceaccount.com"
)

# Configure Service Account Impersonation
logging.info(f"Setting up credential impersonation for: {TARGET_SERVICE_ACCOUNT}")
try:
    source_credentials, _ = default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=TARGET_SERVICE_ACCOUNT,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    logging.info("Successfully generated impersonated credentials.")
except Exception as e:
    logging.critical(f"Failed to generate impersonated credentials: {e}")
    sys.exit(1)

# Initialize GCP Clients with impersonated credentials
storage_client = storage.Client(credentials=creds)
dlp_client = dlp_v2.DlpServiceClient(credentials=creds)

def download_csv_from_gcs(bucket_name, file_name):
    """Downloads CSV content directly from Google Cloud Storage."""
    logging.info(f"Downloading configuration CSV from gs://{bucket_name}/{file_name}...")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    
    # Read text directly into memory
    content = blob.download_as_text()
    return content.splitlines()

def create_inspect_templates_from_csv():
    """Reads CSV from GCS and dynamically creates DLP Inspect Templates across projects."""
    templates = defaultdict(lambda: {'built_in': [], 'custom': []})

    try:
        csv_lines = download_csv_from_gcs(GCS_BUCKET_NAME, CSV_FILE_NAME)
        reader = csv.DictReader(csv_lines)
        
        for row in reader:
            # Extract Target Project & Template Metadata
            project_id = row.get("project_id", "").strip()
            template_id = row.get("template_id", "").strip()
            display_name = row.get("display_name", "").strip()
            description = row.get("description", "").strip()
            region = row.get("region", "global").strip() # Defaults to 'global'
            
            # Extract InfoType Data
            category = row.get("info_type_category", "").strip().upper()
            name = row.get("name", "").strip()
            pattern = row.get("regex_pattern", "").strip()

            # Skip invalid rows
            if not project_id or not template_id:
                logging.warning("Skipping row: Missing project_id or template_id.")
                continue 

            # Group into the correct list based on category
            if category == "BUILTIN":
                templates[(project_id, template_id, display_name, description, region)]['built_in'].append({"name": name})
            elif category == "CUSTOM":
                templates[(project_id, template_id, display_name, description, region)]['custom'].append({
                    "info_type": {"name": name},
                    "regex": {"pattern": pattern}
                })
            else:
                logging.warning(f"Skipping unknown category '{category}' for InfoType: {name}")
                
    except Exception as e:
        logging.error(f"Failed to fetch or parse CSV from GCS bucket '{GCS_BUCKET_NAME}': {e}")
        raise

    logging.info(f"Found {len(templates)} unique templates to create.")

    # Iterate over the grouped templates and push them to GCP
    for (project_id, template_id, display_name, description, region), infotypes in templates.items():
        parent = f"projects/{project_id}/locations/{region}"
        
        # 1. Build the Inspect Config
        inspect_config = {
            "info_types": infotypes['built_in'],
            "custom_info_types": infotypes['custom'],
            "min_likelihood": dlp_v2.Likelihood.LIKELY,
        }

        # 2. Wrap it in a Template object
        inspect_template = {
            "display_name": display_name,
            "description": description,
            "inspect_config": inspect_config
        }

        # 3. Create the template in GCP
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