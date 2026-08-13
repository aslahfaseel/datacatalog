import csv
import logging
import os
from collections import defaultdict
from google.cloud import dlp_v2

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def create_inspect_templates_from_csv(csv_file_path):
    """Reads a CSV for CUSTOM InfoTypes and merges them with hardcoded BUILTIN types."""
    dlp_client = dlp_v2.DlpServiceClient()
    
    # Dictionary to group custom info types by their template definition
    # Key: (project_id, template_id, display_name, description, region)
    # Value: {'custom': []}
    templates = defaultdict(lambda: {'custom': []})

    logging.info(f"Reading template configuration from {csv_file_path}...")
    
    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
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

                # Process only CUSTOM types from the CSV
                if category == "CUSTOM" and name and pattern:
                    templates[(project_id, template_id, display_name, description, region)]['custom'].append({
                        "info_type": {"name": name},
                        "regex": {"pattern": pattern}
                    })
                elif category == "BUILTIN":
                    logging.info(f"Ignoring BUILTIN definition from CSV ({name}); using hardcoded list instead.")
                elif not category:
                    # Captures template metadata even if no custom types are defined
                    pass 
                else:
                    logging.warning(f"Skipping unknown category '{category}' for InfoType: {name}")
                    
    except FileNotFoundError:
        logging.error(f"CSV file not found at path: {csv_file_path}")
        return

    logging.info(f"Found {len(templates)} unique templates to create.")

    # Format the hardcoded built-in info types once
    formatted_builtins = [{"name": info_type} for info_type in BUILTIN_INFO_TYPES]

    # Iterate over the grouped templates and push them to GCP
    for (project_id, template_id, display_name, description, region), infotypes in templates.items():
        # Build the exact GCP resource path dynamically
        parent = f"projects/{project_id}/locations/{region}"
        
        # 1. Build the Inspect Config (Merge hardcoded built-ins with CSV custom rules)
        inspect_config = {
            "info_types": formatted_builtins,
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
            # Catch errors (like "Template already exists" or permission issues) and continue
            logging.error(f"Failed to create template '{template_id}' in project '{project_id}': {e}")

if __name__ == "__main__":
    CSV_PATH = os.environ.get("CSV_FILE_NAME", "templates_config.csv")
    create_inspect_templates_from_csv(CSV_PATH)