import os
import sys
import re
import yaml
import json
import logging
import pandas as pd
import google.auth
from google.auth import impersonated_credentials
from io import StringIO
from datetime import datetime, timezone
from google.auth.transport.requests import Request
from google.cloud import storage
from google.cloud import bigquery
import google.auth.transport.requests
import requests as http_requests

# ──────────────────────────────────────────────────────────────────────────────
# UNBUFFERED LOGGING TO STDOUT
# ──────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

# ──────────────────────────────────────────────────────────────────────────────
# CREDENTIALS & GCS HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def get_credentials(config):
    source_credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    impersonate_conf = config.get("impersonation", {})
    target_sa = impersonate_conf.get("target_sa", "").strip()

    if target_sa:
        logging.info(f"Impersonating service account: {target_sa}")
        credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=target_sa,
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    else:
        credentials = source_credentials
    credentials.refresh(Request())
    return credentials

def read_csv_from_gcs(bucket_name: str, blob_name: str) -> pd.DataFrame:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    content = blob.download_as_text()
    return pd.read_csv(StringIO(content), dtype=str)

def upload_csv_to_gcs(bucket_name: str, blob_name: str, df: pd.DataFrame):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(df.to_csv(index=False), content_type="text/csv")

# ──────────────────────────────────────────────────────────────────────────────
# RULE LIBRARIES & PARSING
# ──────────────────────────────────────────────────────────────────────────────
RULE_LIBRARY: dict = {
    "raw-table-has-data": {"name": "raw-table-has-data", "dimension": "COMPLETENESS", "type": "table_condition", "sqlExpression": "COUNT(*) > 0"},
    "email-format-valid": {"name": "email-format-valid", "dimension": "VALIDITY", "column": "email", "type": "regex", "threshold": 0.99, "regex": r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"}
}

def parse_dynamic_rule(rule_str: str, index: int) -> dict:
    rule_type, param = rule_str.split(":", 1)
    rule_type = rule_type.strip().lower()
    param = param.strip()

    safe_param = re.sub(r'[^a-zA-Z0-9]', '-', param)[:20].strip('-').lower()
    rule_name = f"{rule_type.replace('_', '-')}-{safe_param}-{index}"

    rule_def = {
        "name": rule_name,
        "type": rule_type,
        "threshold": 1.0
    }

    if rule_type == "uniqueness":
        rule_def["dimension"] = "UNIQUENESS"
        rule_def["column"] = param
    elif rule_type == "non_null":
        rule_def["dimension"] = "COMPLETENESS"
        rule_def["column"] = param
    elif rule_type == "row_condition":
        rule_def["dimension"] = "VALIDITY"
        rule_def["sqlExpression"] = param
    elif rule_type == "table_condition":
        rule_def["dimension"] = "COMPLETENESS"
        rule_def["sqlExpression"] = param
    else:
        raise ValueError(f"Unsupported dynamic rule type: '{rule_type}'.")

    return rule_def

def build_rule_payload(rule: dict) -> dict:
    rtype = rule.get("type", "")
    payload: dict = {"name": rule["name"], "dimension": rule["dimension"]}

    if rule.get("column"): payload["column"] = rule["column"]
    
    if rtype not in ("table_condition", "sql_assertion"):
        payload["threshold"] = rule.get("threshold", 1.0)

    if rtype == "row_condition":
        payload["rowConditionExpectation"] = {"sqlExpression": rule.get("sqlExpression")}
    elif rtype == "table_condition":
        payload["tableConditionExpectation"] = {"sqlExpression": rule.get("sqlExpression")}
    elif rtype == "non_null":
        payload["nonNullExpectation"] = {}
    elif rtype == "uniqueness":
        payload["uniquenessExpectation"] = {}
    elif rtype == "regex":
        payload["regexExpectation"] = {"regex": rule.get("regex")}
    else:
        raise ValueError(f"Unknown rule type '{rtype}'")

    return payload

# ──────────────────────────────────────────────────────────────────────────────
# DATAPLEX REST API & BQ AUDIT
# ──────────────────────────────────────────────────────────────────────────────
def _get_token(credentials) -> str:
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

def _scan_exists(project_id: str, location: str, scan_id: str, token: str) -> bool:
    url = f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{location}/dataScans/{scan_id}"
    return http_requests.get(url, headers={"Authorization": f"Bearer {token}"}).status_code == 200

def _build_scan_body(row: dict, rules: list[dict], config: dict) -> tuple[str, dict]:
    project_id = str(row["project_id"]).strip()
    dataset = str(row["dataset"]).strip()
    table_name = str(row["table_name"]).strip()
    
    bq_resource = f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset}/tables/{table_name}"
    
    # Format scan_id to strict Dataplex naming standard
    ds_clean = re.sub(r'[^a-z0-9-]', '-', dataset.lower())
    tbl_clean = re.sub(r'[^a-z0-9-]', '-', table_name.lower())
    scan_id = f"{ds_clean}-{tbl_clean}-custom-dq"[:63].rstrip('-')
    
    display_name = f"{project_id} - {dataset} - {table_name.replace('_', ' ').title()} - custom dq scan"
    
    schedule_cron = str(row.get("schedule_cron", "")).strip()
    trigger = {"schedule": {"cron": schedule_cron}} if schedule_cron and schedule_cron.lower() != "nan" else {"onDemand": {}}
        
    try:
        sampling = float(str(row.get("sampling_percent", "100")).strip() or "100")
    except ValueError:
        sampling = 100.0

    row_filter = str(row.get("row_filter", "")).strip()
    if not row_filter or row_filter.lower() == "nan":
        row_filter = None

    dq_spec = {
        "samplingPercent": sampling,
        "catalogPublishingEnabled": True,
        "rules": rules,
        "postScanActions": {"bigqueryExport": {"resultsTable": config["dataplex"]["results_bq_table"]}},
    }
    
    if row_filter:
        dq_spec["rowFilter"] = row_filter
        
    body = {
        "displayName": display_name,
        "description": f"Custom DQ scan for {dataset}.{table_name}",
        "labels": {
            "project": "vz",
            "managed_by": "custom-dq-cloud-run",
            "scan_type": "dq-custom",
        },
        "data": {"resource": bq_resource},
        "executionSpec": {"trigger": trigger},
        "dataQualitySpec": dq_spec,
    }
    return scan_id, body

def create_or_update_scan(project_id, location, scan_id, body, token) -> tuple[bool, str]:
    base_url = f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{location}/dataScans"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if _scan_exists(project_id, location, scan_id, token):
        params = {"updateMask": "displayName,description,executionSpec,dataQualitySpec,labels"}
        resp = http_requests.patch(f"{base_url}/{scan_id}", headers=headers, params=params, json=body)
    else:
        params = {"dataScanId": scan_id}
        resp = http_requests.post(base_url, headers=headers, params=params, json=body)
        
    if resp.status_code in (200, 201):
        logging.info(f"Successfully processed scan '{scan_id}' in location '{location}'")
        return True, "SUCCESS"
    
    error_details = f"HTTP {resp.status_code}: {resp.text}"
    logging.error(f"Dataplex REST API Call Failed for scan '{scan_id}': {error_details}")
    return False, error_details

def log_to_bigquery(bq_client: bigquery.Client, table_ref: str, entries: list[dict]):
    if not entries:
        return
    errors = bq_client.insert_rows_json(table_ref, entries)
    if errors:
        logging.error(f"BigQuery streaming insert errors: {errors}")
    else:
        logging.info(f"Logged {len(entries)} entries to {table_ref}")

# ──────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────
def main():
    config = load_config()
    credentials = get_credentials(config)
    gcs_conf = config["gcs"]
    audit_table = config["dataplex"].get("audit_bq_table", "")
    
    bq_client = bigquery.Client(credentials=credentials) if audit_table else None
    
    try:
        df = read_csv_from_gcs(gcs_conf["bucket_name"], gcs_conf["csv_blob"])
    except Exception as exc:
        logging.error(f"Failed to read CSV from GCS: {exc}")
        sys.exit(1)

    required_cols = ["project_id", "location", "dataset", "table_name", "rule_keys"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logging.error(f"CSV missing required columns: {missing}")
        sys.exit(1)
        
    audit_entries: list[dict] = []
    global_failed = False

    for idx, row in df.iterrows():
        row_num = idx + 2
        project_id = str(row.get("project_id", "")).strip()
        location   = str(row.get("location", config["dataplex"]["default_location"])).strip()
        dataset    = str(row.get("dataset", "")).strip()
        table_name = str(row.get("table_name", "")).strip()
        raw_keys   = str(row.get("rule_keys", "")).strip()

        if not all([project_id, location, dataset, table_name, raw_keys]):
            logging.warning(f"Row {row_num}: Missing required fields, skipping.")
            df.at[idx, "status"] = "SKIPPED: Missing fields"
            continue
            
        if str(row.get("status", "")).strip().upper() in ("DONE", "SUCCESS"):
            logging.info(f"Row {row_num}: Already processed. Skipping.")
            continue

        rule_keys = [k.strip() for k in raw_keys.split("|") if k.strip()]
        resolved_rules = []
        unknown_keys = []

        for i, key in enumerate(rule_keys):
            try:
                if ":" in key:
                    rule_def = parse_dynamic_rule(key, i)
                    resolved_rules.append(build_rule_payload(rule_def))
                elif key in RULE_LIBRARY:
                    resolved_rules.append(build_rule_payload(RULE_LIBRARY[key]))
                else:
                    logging.warning(f"Row {row_num}: Rule '{key}' skipped.")
                    unknown_keys.append(key)
            except Exception as exc:
                logging.error(f"Row {row_num}: Error parsing rule '{key}': {exc}")

        if not resolved_rules:
            logging.error(f"Row {row_num}: No valid rules parsed.")
            df.at[idx, "status"] = "FAILED: No valid rules parsed"
            global_failed = True
            continue

        token = _get_token(credentials)
        try:
            scan_id, body = _build_scan_body(row.to_dict(), resolved_rules, config)
        except Exception as exc:
            logging.error(f"Row {row_num}: Body build error: {exc}")
            df.at[idx, "status"] = f"FAILED: Body build error — {exc}"
            global_failed = True
            continue
            
        ok, msg = create_or_update_scan(project_id, location, scan_id, body, token)
        
        status_val = "DONE" if ok else f"FAILED: {msg[:100]}"
        if unknown_keys and ok:
            status_val = f"DONE (skipped unknown keys: {','.join(unknown_keys)})"
            
        df.at[idx, "status"] = status_val
        if not ok:
            logging.error(f"Row {row_num} [Table: {dataset}.{table_name}] execution failed.")
            global_failed = True

        audit_entries.append({
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "location": location,
            "dataset": dataset,
            "table_name": table_name,
            "scan_id": scan_id,
            "rule_keys": raw_keys,
            "status": status_val,
        })

    upload_csv_to_gcs(gcs_conf["bucket_name"], gcs_conf["csv_blob"], df)
    
    if bq_client and audit_entries:
        log_to_bigquery(bq_client, audit_table, audit_entries)

    if global_failed:
        raise RuntimeError("Custom DQ scan job completed with one or more failures.")

    logging.info("Job complete.")

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        logging.error(f"Execution Error: {err}")
        sys.exit(1)
        