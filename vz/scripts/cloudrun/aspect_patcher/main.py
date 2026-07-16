"""
VZ Aspect Patcher — Cloud Run Job
===================================
This script runs two pipelines in sequence inside one Cloud Run Job:

PIPELINE 1 — Asset Governance Aspects (our original code):
  1. Downloads vz_aspect_assignment.csv from GCS
  2. Stamps vz-asset-governance aspects (owner, domain, lifecycle) onto each BQ table

PIPELINE 2 — Data Classification (manager's code):
  1. Reads scope.yaml to discover target tables
  2. Reads DLP scan results from BigQuery and maps them to classification levels
  3. Stamps data-classification column-level aspects in Dataplex
  4. Attaches BigQuery Policy Tags to lock down sensitive columns

Environment Variables (set by Terraform Cloud Run Job):
  GCS_BUCKET_NAME        : GCS bucket containing the CSV file
  GCS_CSV_PATH           : Path inside the bucket to the CSV
  DATAPLEX_PROJECT_ID    : GCP Project ID where the catalog entries live
  DATAPLEX_LOCATION      : GCP region (e.g. us-central1)
  GOVERNANCE_PROJECT     : GCP Project ID with DLP results and mapping tables
  CURATED_PROJECT        : GCP Project ID for the recommended_classification table
  DLP_RESULTS_TABLE      : Full BQ path to SDP results table
  MAPPING_TABLE          : Full BQ path to infotype_mapping_local table
  RECOMMENDED_TABLE      : Full BQ path to recommended_classification staging table
"""

import csv
import io
import logging
import os
import sys

from google.cloud import bigquery, dataplex_v1, storage

# --- Classification pipeline imports ---
from classify.identify_scope import identify_scope
from classify.update_recommended_classification import update_recommended_classification
from classify.update_dataplex_aspect import update_dataplex_aspects
from classify.attach_policy_tags import attach_policy_tags

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — read from Terraform-injected environment variables
# ─────────────────────────────────────────────────────────────────────────────
GCS_BUCKET_NAME     = os.environ["GCS_BUCKET_NAME"]
GCS_CSV_PATH        = os.environ["GCS_CSV_PATH"]
DATAPLEX_PROJECT_ID = os.environ["DATAPLEX_PROJECT_ID"]
DATAPLEX_LOCATION   = os.environ["DATAPLEX_LOCATION"]
ASPECT_TYPE_ID      = f"projects/{DATAPLEX_PROJECT_ID}/locations/{DATAPLEX_LOCATION}/aspectTypes/vz-asset-governance"
# Map key format required by Dataplex API: "project.location.aspectType"
ASPECT_TYPE_KEY     = f"{DATAPLEX_PROJECT_ID}.{DATAPLEX_LOCATION}.vz-asset-governance"

# Classification pipeline config
GOVERNANCE_PROJECT  = os.environ.get("GOVERNANCE_PROJECT", DATAPLEX_PROJECT_ID)
CURATED_PROJECT     = os.environ.get("CURATED_PROJECT", DATAPLEX_PROJECT_ID)
DLP_RESULTS_TABLE   = os.environ.get("DLP_RESULTS_TABLE", f"{CURATED_PROJECT}.vzdataset.sdp_results")
MAPPING_TABLE       = os.environ.get("MAPPING_TABLE", f"{CURATED_PROJECT}.vzdataset.infotype_mapping_local")
RECOMMENDED_TABLE   = os.environ.get("RECOMMENDED_TABLE", f"{CURATED_PROJECT}.vzdataset.recommended_classification")

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SCOPE_FILE = os.path.join(BASE_DIR, "classify", "scope.yaml")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE 1: Asset Governance Aspect Patching (from CSV)
# ─────────────────────────────────────────────────────────────────────────────
def download_csv_from_gcs() -> list[dict]:
    """Downloads the aspect assignment CSV from GCS and parses it."""
    logger.info(f"Downloading CSV from gs://{GCS_BUCKET_NAME}/{GCS_CSV_PATH}")
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(GCS_CSV_PATH)
    content = blob.download_as_text()
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    logger.info(f"Loaded {len(rows)} table mappings from CSV")
    return rows


def patch_aspect_on_entry(client: dataplex_v1.CatalogServiceClient, row: dict) -> bool:
    """Patches the vz-asset-governance aspect onto a single catalog entry."""
    # Build the Dataplex entry name dynamically using the CSV fields
    project_id = row.get("project_id", DATAPLEX_PROJECT_ID).strip()
    location   = row.get("location", DATAPLEX_LOCATION).strip()
    dataset_id = row.get("dataset_id", "").strip()
    table_id   = row.get("asset_id", "").strip()
    
    bq_resource = f"bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}"
    entry_name  = f"projects/{project_id}/locations/{location}/entryGroups/@bigquery/entries/{bq_resource}"
    
    owner      = row.get("owner", "").strip()
    domain     = row.get("domain", "").strip()
    lifecycle  = row.get("lifecycle", "").strip()

    try:
        request = dataplex_v1.UpdateEntryRequest(
            entry=dataplex_v1.Entry(
                name=entry_name,
                aspects={
                    ASPECT_TYPE_KEY: dataplex_v1.Aspect(
                        aspect_type=ASPECT_TYPE_ID,
                        data={
                            "owner":     owner,
                            "domain":    domain,
                            "lifecycle": lifecycle,
                        },
                    )
                },
            ),
            update_mask="aspects",
            aspect_keys=[ASPECT_TYPE_KEY],
        )
        client.update_entry(request=request)
        logger.info(f"✅  Patched: {entry_name} → owner={owner}, domain={domain}, lifecycle={lifecycle}")
        return True
    except Exception as e:
        logger.error(f"❌  Failed to patch {entry_name}: {e}")
        return False


def run_asset_governance_pipeline():
    """Pipeline 1: Stamp vz-asset-governance aspects from the CSV file."""
    logger.info("=== PIPELINE 1: Asset Governance Aspect Patching ===")
    rows = download_csv_from_gcs()
    if not rows:
        logger.warning("CSV is empty. Skipping Pipeline 1.")
        return

    client = dataplex_v1.CatalogServiceClient()
    success_count = 0
    failure_count = 0

    for row in rows:
        if patch_aspect_on_entry(client, row):
            success_count += 1
        else:
            failure_count += 1

    logger.info(f"Pipeline 1 Complete — ✅ {success_count} patched, ❌ {failure_count} failed")
    return failure_count


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE 2: Data Classification (DLP → Aspects + Policy Tags)
# ─────────────────────────────────────────────────────────────────────────────
def run_classification_pipeline():
    """Pipeline 2: DLP-based data classification with Dataplex aspects and Policy Tags."""
    logger.info("=== PIPELINE 2: Data Classification Pipeline ===")

    try:
        targets = identify_scope(SCOPE_FILE)
        if not targets:
            logger.warning("No targets identified in scope.yaml. Skipping Pipeline 2.")
            return 0

        total_dataplex_updates = 0
        total_policy_tag_updates = 0

        # Step 2a: Only overwrite recommended_classification if sdp_results has data.
        # If sdp_results is empty (scanner hasn't run yet), preserve existing rows
        # in recommended_classification so manual test data or prior run data is usable.
        bq_check = bigquery.Client(project=GOVERNANCE_PROJECT)
        sdp_check_query = f"SELECT COUNT(*) as cnt FROM `{DLP_RESULTS_TABLE}`"
        sdp_row_count = list(bq_check.query(sdp_check_query).result())[0].cnt

        if sdp_row_count > 0:
            logger.info(f"sdp_results has {sdp_row_count} rows — running classification aggregation.")
            update_recommended_classification(
                governance_project=GOVERNANCE_PROJECT,
                curated_project=CURATED_PROJECT,
                target_project_id=targets[0]["project_id"],
                location=DATAPLEX_LOCATION,
                dataset_id=targets[0]["dataset_id"],
                table_id=targets[0]["table_id"],
                mapping_table=MAPPING_TABLE,
                recommended_table=RECOMMENDED_TABLE,
                dlp_results_table=DLP_RESULTS_TABLE,
            )
        else:
            logger.warning("sdp_results is empty — skipping CREATE OR REPLACE TABLE to preserve existing recommended_classification data.")

        # Step 2b: Stamp aspects and policy tags per table
        for target in targets:
            p_id = target["project_id"]
            d_id = target["dataset_id"]
            t_id = target["table_id"]
            logger.info(f"Classifying: {p_id}.{d_id}.{t_id}")

            dataplex_count = update_dataplex_aspects(
                governance_project=GOVERNANCE_PROJECT,
                target_project_id=p_id,
                curated_project=CURATED_PROJECT,
                location=DATAPLEX_LOCATION,
                recommended_table=RECOMMENDED_TABLE,
                dataset_id=d_id,
                table_id=t_id,
            )
            total_dataplex_updates += dataplex_count

            policy_tag_count, _ = attach_policy_tags(
                governance_project=GOVERNANCE_PROJECT,
                curated_project=CURATED_PROJECT,
                target_project_id=p_id,
                recommended_table=RECOMMENDED_TABLE,
                mapping_table=MAPPING_TABLE,
                dataset_id=d_id,
                table_id=t_id,
            )
            total_policy_tag_updates += policy_tag_count

        logger.info(f"Pipeline 2 Complete — ✅ {total_dataplex_updates} aspects stamped, {total_policy_tag_updates} policy tags applied")
        return 0

    except Exception as e:
        logger.error(f"Pipeline 2 failed: {e}", exc_info=True)
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main():
    logger.info("========== VZ Data Governance Cloud Run Job Starting ==========")
    failures = 0

    failures += run_asset_governance_pipeline() or 0
    failures += run_classification_pipeline() or 0

    logger.info("========== Job Complete ==========")
    if failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
