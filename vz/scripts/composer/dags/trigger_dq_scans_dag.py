"""
Airflow DAG to orchestrate GCP Dataplex Data Quality Scans.
Per the SOW: Trigger DQ scans on a daily schedule (6 AM ET).

This DAG uses the native DataplexRunDataScanOperator to trigger the scan and wait for completion.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.google.cloud.operators.dataplex import DataplexRunDataScanOperator
from airflow.operators.empty import EmptyOperator

# --- CONFIGURATION ---
PROJECT_ID = "dmgcp-del-181"
LOCATION = "us-central1"
# Add all scan IDs here as they get created in Terraform
# Example: vz-raw-dq-daily, vz-raw_order-dq-daily, etc.
DATA_SCANS = [
    "vz-raw-dq-daily",
    "vz-raw-profiling-daily"
]

default_args = {
    "owner": "data_team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["data.alerts@verizon.com"], # Update with actual DL
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "dataplex_dq_scan_orchestration",
    default_args=default_args,
    description="Trigger Dataplex Data Quality & Profiling Scans Daily",
    # 6 AM ET = 10:00 UTC (assuming daylight saving time logic or fixed UTC schedule)
    schedule_interval="0 10 * * *", 
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["dataplex", "data_quality", "knowledge_catalog"],
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    # Dynamically create tasks for each data scan
    for scan_id in DATA_SCANS:
        trigger_scan = DataplexRunDataScanOperator(
            task_id=f"run_scan_{scan_id.replace('-', '_')}",
            project_id=PROJECT_ID,
            region=LOCATION,
            data_scan_id=scan_id,
            asynchronous=False, # Wait for the scan to finish to catch pass/fail status
            deferrable=True,    # Use Airflow deferrable operator to save worker slots while waiting
        )
        
        start >> trigger_scan >> end
