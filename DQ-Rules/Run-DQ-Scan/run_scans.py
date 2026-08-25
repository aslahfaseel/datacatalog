import csv
import io
import os
import re
import uuid
from google.cloud import storage
from google.cloud import dataplex_v1
from google.api_core.exceptions import GoogleAPICallError

# Configuration via Environment Variables
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "dmgcp-del-181")
LOCATION = os.getenv("LOCATION", "us-central1")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
TARGETS_CSV_PATH = os.getenv("TARGETS_CSV_PATH", "dq-targets.csv")

# Target Template Library passed via ENV (Defaults to c360-test)
LIBRARY_ID = os.getenv("LIBRARY_ID", "c360-test")
BQ_RESULTS_TABLE_PATH = os.getenv("BQ_RESULTS_TABLE_PATH")  # Optional: e.g. project.dataset.table

def sanitize_id(name):
    """Converts a rule ID into the standard template entry ID format."""
    base = "".join(c if c.isalnum() else "-" for c in str(name).lower()).strip("-")
    if not base.endswith("template"):
        return f"{base}-template"
    return base

def load_targets_csv():
    """Loads target CSV from GCS or local disk."""
    if GCS_BUCKET_NAME:
        print(f"📥 Fetching targets from gs://{GCS_BUCKET_NAME}/{TARGETS_CSV_PATH}...")
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        content = bucket.blob(TARGETS_CSV_PATH).download_as_text(encoding="utf-8")
        return list(csv.DictReader(io.StringIO(content)))
    elif os.path.exists(TARGETS_CSV_PATH):
        print(f"📂 Loading local targets file: {TARGETS_CSV_PATH}...")
        with open(TARGETS_CSV_PATH, mode='r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    else:
        raise FileNotFoundError(f"Targets CSV file not found at {TARGETS_CSV_PATH}")

def execute_scans():
    targets_reader = load_targets_csv()
    dataplex_client = dataplex_v1.DataScanServiceClient()

    print(f"🎯 Target Template Library set to: '{LIBRARY_ID}'")

    # Group rules by table to generate one scan per BigQuery table
    table_scans = {}

    for row in targets_reader:
        target_project = row['project_id'].strip()
        target_location = row['location'].strip()
        dataset_id = row['dataset_id'].strip()
        table_id = row['table_id'].strip()
        column_name = row.get('column_name', '').strip()
        raw_rule_ids = [r.strip() for r in row['rule_ids'].split(',') if r.strip()]

        table_key = (target_project, target_location, dataset_id, table_id)
        if table_key not in table_scans:
            table_scans[table_key] = []

        for rule_id in raw_rule_ids:
            template_id = sanitize_id(rule_id)

            # Construct fully qualified template path using LIBRARY_ID from ENV
            template_ref_path = (
                f"projects/{PROJECT_ID}/locations/{LOCATION}/"
                f"entryGroups/{LIBRARY_ID}/entries/{template_id}"
            )

            # Define Dataplex DataQualityRule using template_reference
            rule = dataplex_v1.DataQualityRule(
                template_reference=dataplex_v1.DataQualityRule.TemplateReference(
                    name=template_ref_path
                )
            )

            if column_name:
                rule.column = column_name

            table_scans[table_key].append(rule)

    # Trigger scans per target table
    for (target_project, target_location, dataset_id, table_id), scan_rules in table_scans.items():
        if not scan_rules:
            print(f"⏭️ Skipping {table_id}: No rules provided.")
            continue

        execution_spec = None
        if BQ_RESULTS_TABLE_PATH:
            try:
                bq_proj, bq_dataset, bq_table = BQ_RESULTS_TABLE_PATH.split('.')
                bq_export = dataplex_v1.DataScan.ExecutionSpec.PostScanActions.BigQueryExport(
                    dataset=f"projects/{bq_proj}/datasets/{bq_dataset}",
                    table=bq_table
                )
                execution_spec = dataplex_v1.DataScan.ExecutionSpec(
                    post_scan_actions=dataplex_v1.DataScan.ExecutionSpec.PostScanActions(bigquery_export=bq_export)
                )
            except ValueError:
                print("❌ Invalid BQ_RESULTS_TABLE_PATH format. Must be 'project.dataset.table'.")

        clean_table_id = re.sub(r'[^a-z0-9-]', '-', table_id.lower()).strip('-')
        scan_id = f"dq-{clean_table_id}-{uuid.uuid4().hex[:6]}"
        parent = f"projects/{target_project}/locations/{target_location}"
        target_resource = f"//bigquery.googleapis.com/projects/{target_project}/datasets/{dataset_id}/tables/{table_id}"

        data_scan = dataplex_v1.DataScan(
            data_quality_spec=dataplex_v1.DataQualitySpec(rules=scan_rules),
            data=dataplex_v1.DataSource(resource=target_resource)
        )
        if execution_spec:
            data_scan.execution_spec = execution_spec

        request = dataplex_v1.CreateDataScanRequest(
            parent=parent, 
            data_scan=data_scan, 
            data_scan_id=scan_id
        )

        try:
            print(f"\n🚀 Creating DataScan '{scan_id}' targeting library '{LIBRARY_ID}'...")
            operation = dataplex_client.create_data_scan(request=request)
            scan_result = operation.result()

            print(f"⚡ Triggering execution for scan: {scan_result.name}")
            dataplex_client.run_data_scan(request=dataplex_v1.RunDataScanRequest(name=scan_result.name))
            print(f"✅ Successfully submitted scan for table '{table_id}'!")

        except GoogleAPICallError as e:
            print(f"❌ Error executing scan for {table_id}: {e.message}")

if __name__ == "__main__":
    execute_scans()