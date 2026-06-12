import logging
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import google.auth
from google.auth.transport.requests import Request
import json
import pandas as pd
from google.cloud import bigquery, storage

from airflow import DAG
from datetime import datetime
from airflow.operators.python_operator import PythonOperator
from airflow.models import Variable

# ─── Configure Logger ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# ─── Auth ─────────────────────────────────────────────────────────────────────
def get_access_token():
    """Gets ADC access token for Dataplex API calls."""
    credentials, project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    return credentials.token


# ─── Strip routing keys, keep only aspect field values ────────────────────────
def get_payload(payload_dict):
    """
    Removes CSV routing columns (project_id, location, etc.) from the row.
    The remaining columns (owner, domain, lifecycle) become aspect field data.
    """
    keys_to_remove = {
        "project_id",
        "location",
        "entry_group",
        "dataset_id",
        "asset_id",
        "exclude_asset_id",
        "aspect_type_id",
    }
    return {k: v for k, v in payload_dict.items() if k not in keys_to_remove}


# ─── Main DAG Function ────────────────────────────────────────────────────────
def assign_aspect_types():
    """
    Reads GCS CSV, resolves all target tables, and patches vz-asset-governance
    aspect metadata onto each Dataplex Knowledge Catalog entry.

    CSV Column Reference:
      project_id      | GCP project           | dmgcp-del-181
      location        | Region                | us-central1
      entry_group     | Dataplex entry group  | @bigquery
      dataset_id      | BQ dataset            | vzdataset
      asset_id        | Table(s) or *         | raw OR * for all tables
      exclude_asset_id| Tables to skip (opt.) | raw_temp
      aspect_type_id  | Aspect type name      | vz-asset-governance
      owner           | Aspect field value    | Network Analytics Team
      domain          | Aspect field value    | network
      lifecycle       | Aspect field value    | active
    """
    # Read Airflow variables (set these in the Composer UI or via Terraform)
    gcs_bucket_name     = Variable.get("vz_gcs_bucket")
    gcs_assign_aspect_csv = Variable.get("vz_aspect_csv_path")

    bq_client = bigquery.Client()
    df = pd.read_csv(f"gs://{gcs_bucket_name}/{gcs_assign_aspect_csv}")
    df_dict = df.to_dict("records")

    status_code_list = []
    required_keys = ["project_id", "location", "entry_group", "dataset_id", "asset_id"]

    for item in df_dict:
        # Validate required columns are present and filled
        if not all(
            key in item and item[key] is not None and item[key] != ""
            for key in required_keys
        ):
            logging.warning("WARNING | Missing mandatory fields — skipping row: %s", item)
            continue

        project_id   = item.get("project_id")
        location     = item.get("location")
        entry_group  = item.get("entry_group")
        dataset_id   = item.get("dataset_id")
        aspect_type_id = item.get("aspect_type_id")

        # Resolve asset_id — supports "*" (all tables) or comma-separated list
        asset_id_raw = item.get("asset_id")
        asset_ids = (
            asset_id_raw.split(",")
            if asset_id_raw and isinstance(asset_id_raw, str)
            else None
        )

        exclude_raw = item.get("exclude_asset_id")
        exclude_ids = (
            exclude_raw.split(",")
            if exclude_raw and isinstance(exclude_raw, str)
            else None
        )

        if asset_ids and asset_ids[0].strip() == "*":
            # Fetch all tables in the dataset
            all_assets = [t.table_id for t in bq_client.list_tables(f"{project_id}.{dataset_id}")]
        else:
            all_assets = [a.strip() for a in asset_ids] if asset_ids else []

        # Apply exclusions
        if exclude_ids:
            all_assets = [a for a in all_assets if a not in exclude_ids]

        if not all_assets:
            logging.warning("WARNING | No assets resolved for row: %s", item)
            continue

        # Strip routing fields — remaining columns become aspect data payload
        payload = get_payload(item)

        for table_id in all_assets:
            logging.info("INFO | Patching aspect on %s.%s.%s", dataset_id, table_id, aspect_type_id)
            code = push_aspect(
                project_id, location, entry_group,
                dataset_id, table_id, aspect_type_id, payload
            )
            status_code_list.append(code)

    # ─── Archive CSV after processing ─────────────────────────────────────────
    storage_client = storage.Client()
    bucket = storage_client.bucket(gcs_bucket_name)
    source_blob = bucket.blob(gcs_assign_aspect_csv)
    source_folder, file_name = gcs_assign_aspect_csv.rsplit("/", 1)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_file_name = f"{file_name}_{timestamp}"

    failed = [str(c) for c in status_code_list if not str(c).startswith("2")]
    dest_folder = f"{source_folder}/archive/{'failure' if failed else 'success'}"
    destination_blob_name = f"{dest_folder}/{new_file_name}"

    try:
        new_blob = bucket.copy_blob(source_blob, bucket, destination_blob_name)
        if bucket.get_blob(destination_blob_name):
            logging.info("INFO | CSV archived to %s", destination_blob_name)
            source_blob.delete()
            logging.info("INFO | Original CSV deleted: %s", gcs_assign_aspect_csv)
        else:
            raise RuntimeError(f"Failed to verify archive at {destination_blob_name}")
    except Exception as e:
        logging.error("ERROR | GCS file operation failed: %s", str(e))
        raise RuntimeError(f"GCS file operation failed: {str(e)}")


# ─── API Call: Patch Aspect onto Knowledge Catalog Entry ──────────────────────
def push_aspect(project_id, location, entry_group, dataset_id, table_id, aspect_type_id, payload):
    """
    Calls the Dataplex API to attach (or update) an aspect on a Knowledge Catalog entry.
    """
    url = (
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{location}"
        f"/entryGroups/{entry_group}/entries/"
        f"bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}"
        f"?updateMask=aspects"
    )
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }
    body = {
        "aspects": {
            f"{project_id}.{location}.{aspect_type_id}": {"data": payload}
        }
    }

    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = session.patch(url, headers=headers, json=body)
        if response.status_code == 200:
            logging.info("INFO | Aspect patched successfully for %s.%s", dataset_id, table_id)
        else:
            logging.error("ERROR | Aspect patch failed for %s: %s", table_id, json.dumps(response.json()))
            raise RuntimeError(f"Aspect patch failed: {response.status_code}")
        return response.status_code
    except requests.exceptions.RequestException as e:
        logging.error("ERROR | Request failed: %s", str(e))
        raise RuntimeError(f"Request failed: {str(e)}")


# ─── Airflow DAG Definition ───────────────────────────────────────────────────
dag = DAG(
    "vz_assign_asset_governance_aspects",
    description="Assigns vz-asset-governance aspect (owner/domain/lifecycle) to all VZ BigQuery tables",
    schedule_interval=None,  # Triggered manually or when CSV is uploaded
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["vz", "knowledge-catalog", "governance"],
)

push_aspect_assign_task = PythonOperator(
    task_id="assign_vz_asset_governance",
    python_callable=assign_aspect_types,
    dag=dag,
)

push_aspect_assign_task
