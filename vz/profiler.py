import logging
import time
import uuid
import google.auth
from google.auth.transport.requests import Request
from google.cloud import bigquery
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProfiler:

  def __init__(self, project_id: str, location: str = "us-central1"):
    self.project_id = project_id
    self.location = location
    self.credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    self.bq_client = bigquery.Client(
        project=project_id, credentials=self.credentials
    )
    self.base_url = f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{location}"
    self.root_url = "https://dataplex.googleapis.com/v1/"

    # Configure robust exponential backoff and retry logic for connection and server errors
    self.session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=[
            "HEAD",
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
            "TRACE",
        ],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    self.session.mount("https://", adapter)
    self.session.mount("http://", adapter)

  def _get_access_token(self) -> str:
    self.credentials.refresh(Request())
    return self.credentials.token

  def _get_headers(self) -> dict:
    token = self._get_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

  def wait_for_operation(self, operation_name: str, timeout_seconds: int = 300):
    """Polls a long-running operation until complete."""
    start_time = time.time()
    url = f"{self.root_url}{operation_name}"

    logger.info(f"Waiting for operation '{operation_name}' to complete...")
    while time.time() - start_time < timeout_seconds:
      response = self.session.get(url, headers=self._get_headers())
      response.raise_for_status()
      data = response.json()

      if data.get("done"):
        if "error" in data:
          raise Exception(f"Operation failed: {data['error']}")
        logger.info("Operation completed successfully.")
        return data

      time.sleep(5)

    raise Exception(f"Timeout waiting for operation {operation_name}")

  def create_data_profile_scan(
      self,
      dataset_id: str,
      table_id: str,
      datascan_id: str,
      exclude_strings: bool = False,
      additional_exclude_fields: list = None,
  ) -> dict:
    """Creates a Data Profiling DataScan for a given BigQuery table."""
    url = f"{self.base_url}/dataScans?dataScanId={datascan_id}"
    table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
    table = self.bq_client.get_table(table_ref)

    exclude_fields = []
    table_api = table.to_api_repr()
    # Check if table has defaultCollation set to case-insensitive (implicit for all string columns)
    is_default_ci = table_api.get("defaultCollation") == "und:ci"
    if is_default_ci:
      logger.info(
          f"Table '{table_id}' has default case-insensitive collation."
          " Excluding all STRING columns from profiling."
      )

    for field in table.schema:
      field_api = field.to_api_repr()
      field_collation = field_api.get("collation")
      if (
          field_collation == "und:ci"
          or (is_default_ci and field.field_type == "STRING")
          or (exclude_strings and field.field_type == "STRING")
      ):
        logger.info(
            f"Excluding field '{field.name}' from profiling due to"
            f" case-insensitive collation ({field_collation}) or force exclude."
        )
        exclude_fields.append(field.name)

    if additional_exclude_fields:
      for f in additional_exclude_fields:
        if f not in exclude_fields:
          logger.info(f"Excluding failed field '{f}' from retry scan.")
          exclude_fields.append(f)

    payload = {
        "data": {
            "resource": (
                f"//bigquery.googleapis.com/projects/{self.project_id}/datasets/{dataset_id}/tables/{table_id}"
            )
        },
        "executionSpec": {"trigger": {"onDemand": {}}},
        "type": "DATA_PROFILE",
        "dataProfileSpec": {},
    }

    if exclude_fields:
      payload["dataProfileSpec"]["excludeFields"] = {
          "fieldNames": exclude_fields
      }

    logger.info(
        f"Creating Data Profiling scan '{datascan_id}' for table"
        f" '{table_id}'..."
    )
    response = self.session.post(url, headers=self._get_headers(), json=payload)

    if response.status_code == 409:
      logger.info(
          f"DataScan '{datascan_id}' already exists. Proceeding with existing"
          " scan."
      )
      get_url = f"{self.base_url}/dataScans/{datascan_id}"
      return self.session.get(get_url, headers=self._get_headers()).json()

    response.raise_for_status()
    data = response.json()

    # Wait for the long-running Operation to complete
    op_name = data.get("name")
    if op_name and "/operations/" in op_name:
      self.wait_for_operation(op_name)

    return data

  def run_data_profile_scan(self, datascan_id: str) -> dict:
    """Triggers an on-demand run for the created Data Profiling scan."""
    url = f"{self.base_url}/dataScans/{datascan_id}:run"
    logger.info(f"Running DataScan '{datascan_id}'...")
    response = self.session.post(url, headers=self._get_headers())
    response.raise_for_status()
    return response.json()

  def wait_for_job_completion(
      self, datascan_id: str, job_id: str, timeout_seconds: int = 300
  ) -> tuple:
    """Waits for the DataScan job to complete."""
    url = f"{self.base_url}/dataScans/{datascan_id}/jobs/{job_id}"
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
      response = self.session.get(url, headers=self._get_headers())
      response.raise_for_status()
      data = response.json()
      state = data.get("state")

      logger.info(f"Job '{job_id}' state: {state}")
      if state == "SUCCEEDED":
        return True, data
      elif state in ["FAILED", "CANCELLED"]:
        logger.error(f"Job '{job_id}' ended with status: {state}")
        logger.error(f"Failure message: {data.get('message')}")
        return False, data

      time.sleep(10)

    logger.warning(f"Timeout reached while waiting for job '{job_id}'.")
    return False

  def attach_profiling_labels(
      self, dataset_id: str, table_id: str, datascan_id: str
  ):
    """Attaches the necessary data profiling labels to the BigQuery table."""
    table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
    logger.info(f"Attaching profiling labels to table '{table_ref}'...")
    table = self.bq_client.get_table(table_ref)

    labels = table.labels.copy() if table.labels else {}
    labels["dataplex-dp-published-scan"] = datascan_id
    labels["dataplex-dp-published-project"] = self.project_id
    labels["dataplex-dp-published-location"] = self.location

    table.labels = labels
    self.bq_client.update_table(table, ["labels"])
    logger.info(f"Successfully attached labels to table '{table_ref}'.")

  def profile_table(
      self,
      dataset_id: str,
      table_id: str,
      wait_for_completion: bool = True,
      exclude_strings: bool = False,
  ):
    """High-level workflow to fully profile a table with iterative self-healing retries."""
    import re

    safe_dataset = dataset_id[:15].replace("_", "-").lower()
    safe_table = table_id[:25].replace("_", "-").lower()

    additional_excludes = []
    max_fallback_attempts = 5

    for attempt in range(max_fallback_attempts):
      datascan_id = f"dp-{safe_dataset}-{safe_table}-{uuid.uuid4().hex[:6]}"
      logger.info(
          f"Data Profiling attempt {attempt + 1}/{max_fallback_attempts} for"
          f" '{table_id}'"
      )

      self.create_data_profile_scan(
          dataset_id,
          table_id,
          datascan_id,
          exclude_strings=exclude_strings,
          additional_exclude_fields=additional_excludes,
      )
      run_info = self.run_data_profile_scan(datascan_id)

      job = run_info.get("job")
      if job and wait_for_completion:
        job_id = job.get("name", "").split("/")[-1]
        if job_id:
          success, data = self.wait_for_job_completion(datascan_id, job_id)
          if success:
            self.attach_profiling_labels(dataset_id, table_id, datascan_id)
            return
          else:
            # Parse failed columns for the next attempt
            msg = data.get("message", "")
            match = re.search(r"column\(s\) (.*?):", msg)
            if match:
              failed_cols_str = match.group(1)
              failed_cols = [
                  c.strip()
                  for c in re.split(r",|-", failed_cols_str)
                  if c.strip()
              ]

              logger.warning(
                  "Scan failed on specific columns. Adding to exclusions for"
                  f" next attempt: {failed_cols}"
              )
              # Add newly failed columns to the exclusion list
              for col in failed_cols:
                if col not in additional_excludes:
                  additional_excludes.append(col)

              # Proceed to loop and try again with expanded exclusion list
              continue

            logger.error(
                f"Scan '{datascan_id}' did not complete successfully due to"
                " non-parseable error. Labels won't be attached."
            )
            raise Exception("DataScan job failed with non-parseable error.")
      else:
        # If not waiting for completion or no job returned, assume triggered successfully
        self.attach_profiling_labels(dataset_id, table_id, datascan_id)
        return

    logger.error(
        f"Exceeded maximum fallback attempts ({max_fallback_attempts}) for"
        f" table '{table_id}'. Labels won't be attached."
    )
    raise Exception(
        f"DataScan job failed after {max_fallback_attempts} attempts."
    )


if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser(
      description="Profile a BigQuery table with Dataplex DataScans"
  )
  parser.add_argument("--project-id", required=True, help="GCP Project ID")
  parser.add_argument("--dataset-id", required=True, help="BigQuery Dataset ID")
  parser.add_argument("--table-id", required=True, help="BigQuery Table ID")
  parser.add_argument(
      "--location", default="us-central1", help="Dataplex Location"
  )
  args = parser.parse_args()

  profiler = DataProfiler(args.project_id, args.location)
  profiler.profile_table(args.dataset_id, args.table_id)