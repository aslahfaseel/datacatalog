import os
import csv
from google.cloud import storage, dlp_v2
from google.api_core import exceptions
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def download_csv(bucket_name, blob_name, local_path):
    logging.info(f"Downloading {blob_name} from gs://{bucket_name} to {local_path}...")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(local_path)
    logging.info("Download complete.")

def create_stored_infotypes_from_csv(dlp_client, project_id, location, csv_filepath):
    parent = f"projects/{project_id}/locations/{location}"
    
    with open(csv_filepath, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            infotype_id = row["id"].strip()
            display_name = row["display_name"].strip()
            description = row["description"].strip()
            pattern = row["pattern"].strip()

            if not infotype_id or not pattern:
                continue

            stored_info_type_config = {
                "display_name": display_name,
                "description": description,
                "regex": {"pattern": pattern}
            }
            
            try:
                response = dlp_client.create_stored_info_type(
                    request={
                        "parent": parent,
                        "config": stored_info_type_config,
                        "stored_info_type_id": infotype_id
                    }
                )
                logging.info(f"Created Stored InfoType: {response.name}")
            except (exceptions.AlreadyExists, exceptions.InvalidArgument) as e:
                if "already exists" in str(e).lower():
                    logging.info(f"Stored InfoType '{infotype_id}' already exists. Skipping.")
                else:
                    raise e

def create_comprehensive_inspect_template(dlp_client, project_id, location, template_id):
    parent = f"projects/{project_id}/locations/{location}"
    
    # 1. Map Custom Stored InfoTypes based on Alberto's design
    custom_stored_infotypes_meta = [
        {"name": "CUSTOM_ID", "id": "custom-id"},
        {"name": "CORP_SEC_INVESTIGATION_REPORTS", "id": "corp-security-investigation"},
        {"name": "THIRD_PARTY_DEMOGRAPHICS", "id": "third-party-demographics"},
        {"name": "THIRD_PARTY_BRAND_PROP", "id": "third-party-brand-propensities"}
    ]

    custom_info_types = []
    for item in custom_stored_infotypes_meta:
        custom_info_types.append({
            "info_type": {"name": item["name"]},
            "stored_type": {
                "name": f"projects/{project_id}/locations/{location}/storedInfoTypes/{item['id']}"
            }
        })

    # 2. Define the exact builtin list from Alberto's template
    built_in_names = [
        "ADVERTISING_ID","AGE","AUTH_TOKEN","BASIC_AUTH_HEADER","BLOOD_TYPE", "COUNTRY_DEMOGRAPHIC","CREDIT_CARD_DATA","CREDIT_CARD_EXPIRATION_DATE",
        "CREDIT_CARD_NUMBER","CREDIT_CARD_TRACK_NUMBER","CRIME_STATUS","CVV_NUMBER","DATE",
        "DATE_OF_BIRTH","DEMOGRAPHIC_DATA","DOCUMENT_TYPE/CONTEXT/FINANCE", "DOCUMENT_TYPE/CONTEXT/LEGAL",
        "DOCUMENT_TYPE/FINANCE/INVOICE","DOCUMENT_TYPE/FINANCE/REGULATORY","DOCUMENT_TYPE/FINANCE/SEC_FILING",
        "DOCUMENT_TYPE/HR/RESUME","DOCUMENT_TYPE/LEGAL/LAW","DOCUMENT_TYPE/R&D/PATENT",
        "DOCUMENT_TYPE/R&D/SOURCE_CODE","DOD_ID_NUMBER","DOMAIN_NAME","DRIVERS_LICENSE_NUMBER",
        "EMAIL_ADDRESS","EMPLOYMENT_STATUS","ENCRYPTION_KEY","ETHNIC_GROUP","FDA_CODE","FEMALE_NAME",
        "FINANCIAL_ACCOUNT_NUMBER","FINANCIAL_ID","FIRST_NAME","GCP_API_KEY","GCP_CREDENTIALS",
        "GENDER","GENERIC_ID","GEOGRAPHIC_DATA","GOVERNMENT_ID","IBAN_CODE","ICCID_NUMBER",
        "ICD10_CODE","ICD9_CODE","IMEI_HARDWARE_ID","IMSI_ID","IP_ADDRESS","JSON_WEB_TOKEN",
        "LAST_NAME","LOCATION","LOCATION_COORDINATES","MAC_ADDRESS","MAC_ADDRESS_LOCAL",
        "MAC_ADDRESS_UNIVERSAL","MALE_NAME","MARITAL_STATUS","MEDICAL_DATA","OBJECT_TYPE/LICENSE_PLATE",
        "OBJECT_TYPE/PERSON","OBJECT_TYPE/PERSON/PASSPORT","OBJECT_TYPE/PERSON/PHOTO_ID_CARD",
        "ORGANIZATION_NAME","PASSPORT","PASSWORD","PERSON_NAME","PHONE_NUMBER",
        "RELIGIOUS_TERM","SECURITY_DATA","SEXUAL_ORIENTATION","SSL_CERTIFICATE","STORAGE_SIGNED_POLICY_DOCUMENT",
        "STORAGE_SIGNED_URL","STREET_ADDRESS","SWIFT_CODE","TECHNICAL_ID","TRADE_UNION","URL",
        "US_ADOPTION_TAXPAYER_IDENTIFICATION_NUMBER","US_BANK_ROUTING_MICR","US_DEA_NUMBER",
        "US_DRIVERS_LICENSE_NUMBER","US_EMPLOYER_IDENTIFICATION_NUMBER","US_HEALTHCARE_NPI",
        "US_INDIVIDUAL_TAXPAYER_IDENTIFICATION_NUMBER","US_MEDICARE_BENEFICIARY_ID_NUMBER",
        "US_PASSPORT","US_PREPARER_TAXPAYER_IDENTIFICATION_NUMBER","US_SOCIAL_SECURITY_NUMBER",
        "US_STATE","US_TOLLFREE_PHONE_NUMBER","US_VEHICLE_IDENTIFICATION_NUMBER","USER_NAME",
        "VAT_NUMBER","VEHICLE_IDENTIFICATION_NUMBER","WEAK_PASSWORD_HASH","XSRF_TOKEN"
    ]
    
    info_types = [{"name": name} for name in built_in_names if "/" not in name]

    inspect_config = {
        "info_types": info_types,
        "custom_info_types": custom_info_types,
        "include_quote": True,
        "min_likelihood": dlp_v2.Likelihood.LIKELY
    }

    inspect_template = {
        "display_name": "Test Inspection with Custom and Built-in InfoTypes",
        "description": "Template targeting internal proprietary structures and standard high-risk PII/SPII.",
        "inspect_config": inspect_config,
    }

    try:
        response = dlp_client.create_inspect_template(
            request={
                "parent": parent,
                "inspect_template": inspect_template,
                "template_id": template_id,
            }
        )
        logging.info(f"Successfully created Inspect Template: {response.name}")
    except exceptions.AlreadyExists:
        logging.info(f"Inspect Template '{template_id}' already exists.")

if __name__ == "__main__":
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "dmgcp-del-181")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    TEMPLATE_ID = os.environ.get("DLP_TEMPLATE_ID", "alberto_test_template")
    BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "vz-datacatalog")
    BLOB_NAME = os.environ.get("CSV_FILE_NAME", "infotypes.csv")
    
    LOCAL_CSV = "/tmp/infotypes.csv"
    
    logging.info("Starting Setup Script (alberto-code)...")
    
    # 1. Download CSV
    download_csv(BUCKET_NAME, BLOB_NAME, LOCAL_CSV)
    
    dlp_client = dlp_v2.DlpServiceClient()
    
    # 2. Create Stored InfoTypes
    create_stored_infotypes_from_csv(dlp_client, PROJECT_ID, LOCATION, LOCAL_CSV)
    
    # 3. Create Inspect Template
    create_comprehensive_inspect_template(dlp_client, PROJECT_ID, LOCATION, TEMPLATE_ID)
    
    logging.info("Setup complete. Successfully exited.")
