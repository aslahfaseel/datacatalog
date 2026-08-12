import os
import csv
from google.cloud import dlp_v2
from google.api_core.exceptions import AlreadyExists

def create_stored_infotypes_from_csv(project_id: str, csv_filepath: str, location: str = "global"):
    """Reads custom infotype definitions from a CSV file and creates StoredInfoTypes in GCP DLP."""
    # Initialize the Sensitive Data Protection (DLP) client
    dlp_client = dlp_v2.DlpServiceClient()
    parent = f"projects/{project_id}/locations/{location}"

    if not os.path.exists(csv_filepath):
        print(f"[Error] CSV configuration file not found at: {csv_filepath}")
        return

    print(f"Reading configuration from '{csv_filepath}'...")

    with open(csv_filepath, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        # Verify required headers are present
        required_headers = {"id", "display_name", "description", "pattern"}
        if not required_headers.issubset(set(reader.fieldnames or [])):
            print(f"[Error] CSV must contain headers: {', '.join(required_headers)}")
            return

        for row in reader:
            infotype_id = row["id"].strip()
            display_name = row["display_name"].strip()
            description = row["description"].strip()
            pattern = row["pattern"].strip()

            if not infotype_id or not pattern:
                print(f" -> Skipping row with empty id/pattern: {row}")
                continue

            # Fix: Define the configuration as a dictionary. 
            # The client SDK natively serializes dictionaries into Protobuf structures.
            stored_info_type_config = {
                "display_name": display_name,
                "description": description,
                "regex": {
                    "pattern": pattern
                }
            }

            try:
                print(f"Creating Stored InfoType '{infotype_id}'...")
                response = dlp_client.create_stored_info_type(
                    request={
                        "parent": parent,
                        "config": stored_info_type_config,
                        "stored_info_type_id": infotype_id
                    }
                )
                print(f" -> Successfully created: {response.name}\n")
            except AlreadyExists:
                print(f" -> InfoType '{infotype_id}' already exists. Skipping.\n")
            except Exception as e:
                print(f" -> Error creating '{infotype_id}': {e}\n")


if __name__ == "__main__":
    # Fetch configurations from Environment Variables
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "dmgcp-del-181")
    CSV_FILEPATH = os.environ.get("INFOTYPES_CSV", "infotypes.csv")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    if PROJECT_ID == "your-gcp-project-id":
        print("[Error] Please export GOOGLE_CLOUD_PROJECT before running.")
    else:
        create_stored_infotypes_from_csv(project_id=PROJECT_ID, csv_filepath=CSV_FILEPATH, location=LOCATION)
