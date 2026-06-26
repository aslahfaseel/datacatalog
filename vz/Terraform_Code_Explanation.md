# 📖 Complete Terraform Code Explanation
## Verizon Knowledge Catalog — Spoon-Feeding Guide

This document explains **every single file** in our Terraform project in simple language. Think of each section as a chapter in a story. Each file plays a specific role in the overall automation system.

---

# CHAPTER 1: The Configuration Files (What You Change)

## 📄 `envs/dev/terraform.tfvars` — The Control Panel

This is the **only file a Data Engineer ever needs to open** when adding a new table. It is like a settings panel. You type values here, and all the other files read those values automatically.

```hcl
project_id             = "dmgcp-del-181"
```
**What it does:** Tells Terraform which Google Cloud project to build everything inside. Every resource we create will live inside this project.

```hcl
region   = "us-central1"
location = "us-central1"
```
**What they do:** Tells Terraform which GCP data center (region) to use. Our BigQuery data lives in `us-central1` so everything must be built in the same area.

```hcl
terraform_sa = "vz-datacatalog@dmgcp-del-181.iam.gserviceaccount.com"
```
**What it does:** This is the Robot account (Service Account) that Terraform uses to connect to GCP and build our infrastructure. Think of it like a "builder employee ID card" that gives Terraform permission to work inside the GCP project.

```hcl
dataplex_service_agent = "service-308053638624@gcp-sa-dataplex.iam.gserviceaccount.com"
```
**What it does:** This is a completely different robot — Google's own internal Dataplex robot. When our Dataplex scans run at 6 AM every day, it is THIS robot (not our Terraform robot) that actually reads BigQuery and runs the checks. We need to grant this robot its own permissions separately.

```hcl
dq_profile_scans = {
  raw = {
    project_id               = "dmgcp-del-181"
    region                   = "us-central1"
    existing_profile_scan_id = "vz-raw-profiling-daily"
    new_dq_scan_id           = "vz-raw-dq-profile-based"
  }
}
```
**What it does:** This is the "50-table scaling map". Each item in this map represents one BigQuery table that needs automated DQ rules. Terraform reads this map and creates a separate Data Quality scan for every single entry automatically. To onboard a new table, you simply paste a new block here.

---

## 📄 `envs/dev/providers.tf` — The Plugin Manager

Before Terraform can talk to Google Cloud, it needs the correct "plugins" (providers) installed. This file defines which plugins it needs.

```hcl
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.0"
    }
  }
}
```
- **`hashicorp/google`**: The main plugin that allows Terraform to build Dataplex scans, IAM permissions, and Aspect Types.
- **`hashicorp/google-beta`**: A slightly different version of the Google plugin that has access to newer features that are still in beta (like automatically creating DLP service accounts).
- **`hashicorp/http`**: A plugin that allows Terraform to make REST API calls to the internet. We use this to call the Dataplex API and download AI-recommended DQ rules.

---

## 📄 `envs/dev/variables.tf` — The Declaration Form

While `terraform.tfvars` is where you TYPE the values, this file DECLARES what values are expected to exist. Think of it like a form with blank boxes — this file defines what the boxes are, and `terraform.tfvars` fills them in.

```hcl
variable "project_id" {
  description = "The GCP project ID"
  type        = string
}
```
**What it does:** Tells Terraform "I expect someone to pass me a value called `project_id` and it must be a string of text." If you forget to put `project_id` in `terraform.tfvars`, Terraform will stop and ask you for it.

```hcl
variable "dq_profile_scans" {
  description = "Map of profile-based DQ scans to create"
  type = map(object({
    project_id               = string
    region                   = string
    existing_profile_scan_id = string
    new_dq_scan_id           = string
  }))
  default = {}
}
```
**What it does:** Declares the complex map structure we use for scaling to 50 tables. The `type = map(object({...}))` is essentially a schema that enforces exactly which keys are required inside each entry. If a Data Engineer accidentally forgets to write `region =` in the tfvars, Terraform instantly throws an error pointing to the exact mistake.

---

# CHAPTER 2: The Master Controller (dataplex.tf)

## 📄 `envs/dev/dataplex.tf` — The Orchestrator

This is the most important file. It is the "Master Controller" or "Conductor" of the entire orchestra. It reads all the variables, and it calls all the reusable modules in the correct order.

### Section 1: Local Variables
```hcl
locals {
  bq_prefix             = "//bigquery.googleapis.com/projects/${var.project_id}"
  dq_results_table      = "${local.bq_prefix}/datasets/vzdataset/tables/dq_results"
  profile_results_table = "${local.bq_prefix}/datasets/vzdataset/tables/profiling_results"
  common_labels = {
    project     = "vz"
    environment = "dev"
    managed_by  = "terraform"
  }
}
```
**What it does:** `locals` are like shortcut variables we define for ourselves inside this file only. Instead of typing the full BigQuery path every time, we type it once here and then use `local.bq_prefix` everywhere else. This avoids typos and keeps the code DRY (Don't Repeat Yourself).

### Section 2: MODULE 1 — IAM Setup
```hcl
module "dataplex_iam" {
  source                 = "../../custom_modules/dataplex_iam"
  project_id             = var.project_id
  terraform_sa           = var.terraform_sa
  dataplex_service_agent = var.dataplex_service_agent
}
```
**What it does:** Calls the IAM (permissions) module FIRST, before anything else. This is critically important because ALL other modules depend on having the correct permissions. If they ran before this, they would get 403 Permission Denied errors.
- It passes in the two robot accounts so the IAM module knows exactly who to grant permissions to.

### Section 3: MODULE 2 — Aspect Type (Metadata Standard)
```hcl
module "aspect_type_asset_governance" {
  source          = "../../custom_modules/dataplex_aspect_type"
  aspect_type_id  = "vz-asset-governance"
  metadata_template = jsonencode({
    recordFields = [
      { name = "owner",     type = "string" },
      { name = "domain",    type = "enum"   },
      { name = "lifecycle", type = "enum"   }
    ]
  })
  depends_on = [module.dataplex_iam]
}
```
**What it does:** Creates our governance standard for the Knowledge Catalog. The `metadata_template` is a JSON schema that defines exactly 3 fields every table must have stamped on it: who owns it, which business domain it belongs to, and what stage of life it is in.
- `depends_on = [module.dataplex_iam]`: This line tells Terraform "don't start this module until the IAM module is 100% finished." This enforces the correct build order.

### Section 4: MODULE 3 — Data Profiling Scan
```hcl
module "profiling_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan/data-profiling"
  data_scan_id     = "vz-raw-profiling-daily"
  source_bq_table  = "${local.bq_prefix}/datasets/vzdataset/tables/raw"
  results_bq_table = local.profile_results_table
  schedule_cron    = "0 0 * * *"
}
```
**What it does:** Deploys an automated "Mathematical Analysis" scan on the `vzdataset.raw` table. The `schedule_cron = "0 0 * * *"` means it runs every night at midnight (12:00 AM). This scan records the statistical footprint (Null%, Min, Max, Uniqueness) of every column.

### Section 5: MODULE 4 — Manual DQ Scan
```hcl
module "dq_scan_raw" {
  source       = "../../custom_modules/dataplex_datascan/data-quality"
  data_scan_id = "vz-raw-dq-daily"
  dq_rules = [
    {
      name              = "id-not-null"
      dimension         = "COMPLETENESS"
      row_condition_sql = "id IS NOT NULL"
    }
  ]
}
```
**What it does:** Creates the "Manual Override" DQ scan. This is the fallback option for when the Data Team wants to write their own specific business rules. Here, we manually told it: "Every single row must have a non-null `id` column." If any row violates this, the scan marks that row as FAILED.

### Section 6: MODULE 5 — The AI-Powered DQ Engine (The Star)
This is the most advanced section. It is three separate steps that work together.

**Step A: Get Authentication Token**
```hcl
data "google_client_config" "default" {}
```
This fetches the current Google OAuth2 access token from our logged-in Terraform account. We need this token to make secure API calls.

**Step B: Call the Dataplex REST API**
```hcl
data "http" "profile_scan_details" {
  for_each = var.dq_profile_scans
  url      = "https://dataplex.googleapis.com/v1/projects/.../dataScans/${each.value.existing_profile_scan_id}"
  request_headers = {
    Authorization = "Bearer ${data.google_client_config.default.access_token}"
  }
}
```
For each table in our `dq_profile_scans` map, it makes a secure HTTPS API call to Dataplex and downloads the JSON metadata about the profiling scan. This JSON contains the exact BigQuery table path that the profiler was attached to.

**Step C: Download the AI-generated Rules**
```hcl
data "google_dataplex_data_quality_rules" "recommendations" {
  for_each     = var.dq_profile_scans
  data_scan_id = each.value.existing_profile_scan_id
}
```
This tells Terraform to connect to the `google_dataplex_data_quality_rules` data source (a special Terraform function that talks directly to the Dataplex recommendation engine) and downloads ALL the AI-generated rules for each scan. The result is a list of rule objects — exactly the 7 rules you see in the UI!

**Step D: Build 50 DQ Scans Automatically**
```hcl
resource "google_dataplex_datascan" "dq_from_profile" {
  for_each     = var.dq_profile_scans
  data_scan_id = each.value.new_dq_scan_id

  data_quality_spec {
    catalog_publishing_enabled = true
    dynamic "rules" {
      for_each = data.google_dataplex_data_quality_rules.recommendations[each.key].rules
      content {
        dynamic "non_null_expectation" { ... }
        dynamic "range_expectation"    { ... }
        # ... 7 more rule types
      }
    }
  }
}
```
`for_each = var.dq_profile_scans` means Terraform creates one entire DQ scan for EVERY entry in the 50-table list. Inside it, `dynamic "rules"` loops over every AI rule downloaded in Step C and builds the correct Terraform block for it. `catalog_publishing_enabled = true` sends the Pass/Fail grade directly to the Knowledge Catalog UI.

---

# CHAPTER 3: The Reusable Modules

## 📄 `custom_modules/dataplex_iam/main.tf` — The Security Setup

This module grants the correct permissions to the correct robots.

```hcl
resource "google_project_iam_member" "terraform_dataplex_editor" {
  role   = "roles/dataplex.editor"
  member = "serviceAccount:${var.terraform_sa}"
}
```
**What it does:** Grants the Terraform robot `roles/dataplex.editor` so it has permission to CREATE, UPDATE, and DELETE Dataplex scans and Aspect Types.

```hcl
resource "google_project_iam_member" "dataplex_bq_viewer" {
  role   = "roles/bigquery.dataViewer"
  member = "serviceAccount:${var.dataplex_service_agent}"
}
```
**What it does:** Grants Google's Dataplex scanning robot the `bigquery.dataViewer` role so it can READ the data inside BigQuery tables during the nightly scans. Without this, the scan robot would be blocked by GCP Security.

---

## 📄 `custom_modules/dataplex_aspect_type/main.tf` — The Metadata Blueprint

```hcl
resource "google_dataplex_aspect_type" "this" {
  aspect_type_id    = var.aspect_type_id
  metadata_template = var.metadata_template
}
```
**What it does:** Creates the `vz-asset-governance` template in Google Cloud. After this resource is created, every person who opens any BigQuery table in the Knowledge Catalog will see an "Aspects" tab showing the Owner, Domain, and Lifecycle fields that our Airflow DAG later fills in.

---

## 📄 `custom_modules/dataplex_datascan/data-profiling/main.tf` — The Math Scanner

```hcl
resource "google_dataplex_datascan" "profiling" {
  data_profile_spec {
    catalog_publishing_enabled = true
    post_scan_actions {
      bigquery_export {
        results_table = var.results_bq_table
      }
    }
  }
}
```
**What it does:** Creates a scan that runs mathematical analysis on each column of the BigQuery table.
- `data_profile_spec` switches the scan into "profiling mode" (as opposed to quality mode).
- `catalog_publishing_enabled = true` pushes the statistical results to the Knowledge Catalog UI tab.
- `bigquery_export` also saves the raw results to a BigQuery table (`profiling_results`) for historical tracking and Looker Dashboards.

---

## 📄 `custom_modules/dataplex_datascan/data-quality/main.tf` — The 9-Rule Engine

This is the most complex module. It handles 9 different types of Data Quality rules.

```hcl
dynamic "execution_identity" {
  for_each = var.service_account_email != null ? [1] : []
  content {
    service_account {
      email = var.service_account_email
    }
  }
}
```
**What it does:** The `dynamic` block only activates if `service_account_email` is provided. If someone passes in a custom service account email, the scan uses that specific robot to run. If not, Dataplex uses its own default Google-managed robot. This makes the module flexible for different environments.

```hcl
dynamic "on_demand" {
  for_each = var.schedule_cron == null ? [1] : []
  content {}
}
dynamic "schedule" {
  for_each = var.schedule_cron != null ? [1] : []
  content {
    cron = var.schedule_cron
  }
}
```
**What it does:** Smart scheduling logic. If the caller provides a `schedule_cron`, the scan runs on that schedule automatically. If not, it runs "on demand" only when someone clicks "Run Now" in the GCP UI.

```hcl
dynamic "non_null_expectation" {
  for_each = lookup(rules.value, "non_null_expectation", false) ? [1] : []
  content {}
}
```
**What it does (The Logic Funnel Pattern):** `lookup(rules.value, "non_null_expectation", false)` tries to find `non_null_expectation` inside the current rule. If it finds `true`, the expression returns `[1]` (a list with one item), which causes the `for_each` to activate and BUILD the rule block. If it returns `false`, the `for_each = []` (empty list) means this block is completely skipped. This pattern is repeated 9 times for each rule type, acting like a funnel that only activates the correct plumbing.

---

## 📄 `custom_modules/dataplex_sdp/main.tf` — The Security Scanner (DLP)

```hcl
resource "google_project_service_identity" "dlp_sa" {
  provider = google-beta
  service  = "dlp.googleapis.com"
}
```
**What it does:** Forces Google Cloud to immediately create the DLP robot account before Terraform tries to grant it permissions. Without this, GCP sometimes throws a "That robot doesn't exist yet" error.

```hcl
resource "google_data_loss_prevention_inspect_template" "bq_inspect" {
  parent = "projects/${var.project_id}/locations/us"
  inspect_config {
    info_types { name = "CREDIT_CARD_NUMBER" }
    info_types { name = "EMAIL_ADDRESS"      }
    info_types { name = "US_SOCIAL_SECURITY_NUMBER" }
    info_types { name = "PERSON_NAME"        }
    info_types { name = "PHONE_NUMBER"       }
    info_types { name = "DATE_OF_BIRTH"      }
    min_likelihood = "LIKELY"
  }
}
```
**What it does:** Creates the "Rulebook for sensitive data." It defines 6 types of information the DLP engine must look for. `min_likelihood = "LIKELY"` means "only flag something as sensitive if you are at least 75% confident it is actually sensitive." This avoids false alarms.

```hcl
resource "google_data_loss_prevention_discovery_config" "bq_discovery" {
  inspect_templates = [google_data_loss_prevention_inspect_template.bq_inspect.id]
  targets {
    big_query_target {
      filter { other_tables {} }
    }
  }
  actions {
    publish_to_dataplex_catalog {}
  }
}
```
**What it does:** Creates the actual scanning engine.
- `inspect_templates` links our Rulebook to this engine so it knows what to look for.
- `other_tables {}` means "scan ALL BigQuery tables in the project", not just one.
- `publish_to_dataplex_catalog {}` means whenever DLP finds a Credit Card number, it automatically writes that finding into the Dataplex Knowledge Catalog UI as a badge on the table.

---

## 📄 `custom_modules/cloudrun_aspect_patcher/main.tf` — The Metadata Patcher Job

This module creates a serverless "container job" that wakes up, reads a CSV file containing our Data Catalog aspects (tags), applies those tags to our tables, and goes back to sleep. This replaces Airflow for a cheaper, lighter solution.

```hcl
locals {
  job_sa_member = "serviceAccount:${var.service_account_email}"
}
```
**What it does:** Similar to other files, this creates a shortcut variable inside this file so we don't have to keep re-typing `"serviceAccount:..."` every time we want to reference the service account.

```hcl
resource "google_cloud_run_v2_job" "aspect_patcher" {
  name     = var.job_name
  location = var.location
  project  = var.project_id
  labels   = var.labels
```
**What it does:** This block declares the creation of the actual Cloud Run Job itself. It gives the job a `name`, tells it which `location` (region) to run in, and what `project` it belongs to.

```hcl
  template {
    labels      = var.labels
    parallelism = 1
    task_count  = 1
```
**What it does:** Defines *how* the job should execute. `task_count = 1` and `parallelism = 1` means "run only one container at a time to do this job." We aren't trying to process a billion records simultaneously here, just applying some tags.

```hcl
    template {
      service_account = var.service_account_email
      max_retries     = var.max_retries
      timeout         = "${var.timeout_seconds}s"
```
**What it does:** This inner template gets into the nitty-gritty of the container itself:
- `service_account`: The robot account this container uses to prove its identity (needed to have permission to read BigQuery and update Dataplex).
- `max_retries`: If the job crashes, try it again this many times (usually 3).
- `timeout`: Put a hard limit on how long it can run before GCP kills it (stops runaway costs).

```hcl
      containers {
        image = var.container_image

        env {
          name  = "GCS_BUCKET_NAME"
          value = var.gcs_bucket_name
        }
        env {
          name  = "GCS_CSV_PATH"
          value = var.gcs_csv_path
        }
        # ... (dataplex project and location env vars)
```
**What it does:** This is the core engine!
- `image`: Specifies the pre-built Docker Container image that contains our Python patching script. 
- `env`: These are Environment Variables. Terraform injects these settings (like bucket name and CSV path) INTO the running Python script. This means our Python code doesn't need hardcoded paths; it just reads these variables dynamically.

```hcl
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
```
**What it does:** Limits the computing power of the container. 1 CPU and 512 Megabytes of RAM. This keeps costs incredibly low!

```hcl
resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = local.job_sa_member
}
```
**What it does:** This is a permissions block. It gives our service account the specific right (`run.invoker`) to actually click "Start" on this Cloud Run Job. Without this, even the account that built the job couldn't trigger it! The comments above it note that since we can't create the Cloud Scheduler (cron job) inside Terraform due to permission issues, we leave it to manual triggers or manual scheduler setup.
