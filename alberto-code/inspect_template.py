import os
from google.cloud import dlp_v2
from google.api_core.exceptions import AlreadyExists

def create_comprehensive_inspect_template(
    project_id: str, 
    template_id: str = "test_inspection_template",
    display_name: str = "Test Inspection with Custom and Built-in InfoTypes",
    location: str = "global"
):
    """Creates a GCP DLP Inspect Template compiling both Stored InfoTypes and Built-in ones."""
    # Initialize the Sensitive Data Protection (DLP) client
    dlp_client = dlp_v2.DlpServiceClient()
    
    # 1. Map Custom Stored InfoTypes (using their created IDs from the previous steps)
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

    # 2. Define the complete list of 46 standard Built-in InfoTypes
    built_in_names = [
        "ADVERTISING_ID","AGE","AUTH_TOKEN","BASIC_AUTH_HEADER","BLOOD_TYPE", "COUNTRY_DEMOGRAPHIC","CREDIT_CARD_DATA","CREDIT_CARD_EXPIRATION_DATE",
        "CREDIT_CARD_NUMBER","CREDIT_CARD_TRACK_NUMBER","CRIME_STATUS","CVV_NUMBER","DATE",
        "DATE_OF_BIRTH","DEMOGRAPHIC_DATA","DOCUMENT_TYPE/CONTEXT/FINANCE",	"DOCUMENT_TYPE/CONTEXT/LEGAL",
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
    
    info_types = [{"name": name} for name in built_in_names]

    # 3. Assemble Inspect Configuration
    inspect_config = {
        "info_types": info_types,
        "custom_info_types": custom_info_types,
        "include_quote": True, # Change to False if you don't want found snippets in the results
        "min_likelihood": dlp_v2.Likelihood.LIKELY,
        "allow_limited_availability_info_types": True
    }

    # 4. Formulate overall Inspect Template payload
    inspect_template = {
        "display_name": display_name,
        "description": "Template targeting internal proprietary structures and standard high-risk PII/SPII.",
        "inspect_config": inspect_config,
    }

    parent = f"projects/{project_id}/locations/{location}"

    try:
        print(f"Creating Inspect Template '{template_id}' in location '{location}'...")
        response = dlp_client.create_inspect_template(
            request={
                "parent": parent,
                "inspect_template": inspect_template,
                "template_id": template_id,
            }
        )
        print(f" -> Successfully created Inspect Template: {response.name}")
        return response
    except AlreadyExists:
        print(f" -> Inspect Template '{template_id}' already exists in project '{project_id}'.")
    except Exception as e:
        print(f" -> Failed to create Inspect Template: {e}")

if __name__ == "__main__":
    # Ensure environment variables are loaded
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "dmgcp-del-181")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    TEMPLATE_ID = os.environ.get("DLP_TEMPLATE_ID", "alberto_test_template")
    
    if PROJECT_ID == "central-governance-469014":
        print("[Error] Please export GOOGLE_CLOUD_PROJECT before running.")
    else:
        create_comprehensive_inspect_template(
            project_id=PROJECT_ID, 
            template_id=TEMPLATE_ID,
            location=LOCATION
        )
