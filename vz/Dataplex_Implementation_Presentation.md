# 📊 Verizon Knowledge Catalog: Automated Data Quality & Governance Implementation

**Date:** June 2026  
**Project:** Dataplex Knowledge Catalog (vzdataset)  
**Objective:** Deliver an automated, highly-scalable Data Profile and Data Quality (DQ) infrastructure using Terraform to establish data trust for the enterprise.

---

## 🎯 1. Executive Summary
We have successfully transitioned the Knowledge Catalog infrastructure from a monolithic design into a highly scalable, automated, and production-ready Terraform CI/CD pipeline. 

The highlight of this implementation is the **AI-Driven Data Quality System**: we eliminate the need for data engineers to manually write SQL rules. Instead, the infrastructure automatically reads statistical profiling results and dynamically deploys data quality checks.

---

## 🗺️ 2. Architecture & Automation Flow
*(Note: To render this graph, open this file in VS Code and click the "Open Preview" button in the top right, or paste this block into [Mermaid Live](https://mermaid.live). You can then screenshot the graph to put in your presentation).*

```mermaid
graph TD
    subgraph "Infrastructure & Execution"
        TF[Terraform Pipeline]
        Composer[Composer / Airflow DAG]
    end

    subgraph "GCP Data Storage"
        BQ[(BigQuery Table\n'vzdataset.raw')]
    end

    subgraph "Dataplex Service Layer"
        ProfScan[Data Profiling Scan]
        API((Dataplex AI\nRule Recommendation API))
        DQScan[Data Quality Scan]
        Aspect[vz-asset-governance\nAspect Type]
    end

    subgraph "Business Value Layer"
        Catalog{{Knowledge Catalog UI}}
    end

    %% Flow completely automated by our setup
    TF ==>|1. Deploys| ProfScan
    ProfScan -->|2. Reads Data| BQ
    ProfScan ==>|3. Generates Statistical Footprint| API
    
    TF -.->|4. Fetches Auto-Rules via REST API| API
    TF ==>|5. Deploys using Auto-Rules| DQScan
    DQScan -->|6. Validates Rows & Aggregates| BQ
    
    ProfScan -.->|7. Auto-Publishes Stats| Catalog
    DQScan -.->|8. Auto-Publishes Pass/Fail Badges| Catalog
    
    Composer ==>|9. Patches CSV Mappings| Aspect
    Aspect -.->|10. Tags Data with Owner/Domain| Catalog

    classDef tf fill:#5c4ee5,stroke:#fff,stroke-width:2px,color:#fff;
    classDef bq fill:#4285f4,stroke:#fff,stroke-width:2px,color:#fff;
    classDef catalog fill:#34a853,stroke:#fff,stroke-width:2px,color:#fff;
    classDef dataplex fill:#fbbc05,stroke:#fff,stroke-width:2px,color:#000;
    
    class TF tf;
    class BQ bq;
    class Catalog catalog;
    class ProfScan,API,DQScan,Aspect dataplex;
```

---

## 🏗️ 3. Architectural Advancements

### A. Decoupled, Scalable Infrastructure Modules
*   **What we did:** Split the monolithic Dataplex scan module into independent `data-profiling` and `data-quality` Terraform submodules.
*   **Business Value:** Teams can now run Profiling entirely independently of DQ, saving compute costs and simplifying troubleshooting.

### B. AI-Driven Rule Generation (Profile-Based DQ)
*   **What we did:** Implemented the Dataplex Profile-recommendation pattern utilizing the Dataplex REST API (`hashicorp/http`) and the `google_dataplex_data_quality_rules` data source.
*   **Business Value:** Dataplex now statistically analyzes our data footprint and auto-generates up to **9 different rule types** with zero manual SQL. This drastically accelerates the onboarding of new tables.

### C. Standardized Custom Metadata (Asset Governance)
*   **What we did:** Consolidated complex metadata requirements into exactly **1 standardized Aspect Type**.
*   **Business Value:** Guarantees a single source of truth for table ownership (`owner`, `domain`, `lifecycle`), making the data easily discoverable for GenAI initiatives. 

### D. Native Knowledge Catalog Integration & Scaling to 50 Tables
*   **What we did:** Added `catalog_publishing_enabled = true` so results instantly appear in the Knowledge Catalog. We also built a `for_each` mapping pattern directly into `terraform.tfvars`. To onboard a new table, a developer adds just **4 lines of code** into this list, preventing hundreds of lines of code bloat.

---

# 💻 4. Terraform Codebase Showcase (The Implementation)

Below is the complete Terraform architecture we developed to achieve this automation.

### 📄 1. The Scaling Configuration (`envs/dev/terraform.tfvars`)
*This is the only file data engineers need to edit to onboard a new table into the AI-driven DQ engine. Adding one block creates the entire suite of automated checks.*

```hcl
project_id             = "dmgcp-del-181"
region                 = "us-central1"
location               = "us-central1"
terraform_sa           = "vz-datacatalog@dmgcp-del-181.iam.gserviceaccount.com"
dataplex_service_agent = "service-308053638624@gcp-sa-dataplex.iam.gserviceaccount.com"

# Profile-based DQ scans — add one entry per table to scale up to 50 tables
# existing_profile_scan_id = profiling scan that generated recommendations
# new_dq_scan_id           = new DQ scan Terraform will create automatically
dq_profile_scans = {
  raw = {
    project_id               = "dmgcp-del-181"
    region                   = "us-central1"
    existing_profile_scan_id = "vz-raw-profiling-daily"
    new_dq_scan_id           = "vz-raw-dq-profile-based"
  }
}
```

### 📄 2. The Core Environment Controller (`envs/dev/dataplex.tf`)
*This file wires everything together. Notice "MODULE 5" at the bottom: it dynamically queries the Dataplex API, reads the statistical profile, and instantly generates all Data Quality rules based on AI recommendations.*

```hcl
locals {
  bq_prefix             = "//bigquery.googleapis.com/projects/${var.project_id}"
  dq_results_table      = "${local.bq_prefix}/datasets/vzdataset/tables/dq_results"
  profile_results_table = "${local.bq_prefix}/datasets/vzdataset/tables/profiling_results"
}

# MODULE 1: IAM Setup
module "dataplex_iam" {
  source                 = "../../custom_modules/dataplex_iam"
  project_id             = var.project_id
  terraform_sa           = var.terraform_sa
  dataplex_service_agent = var.dataplex_service_agent
}

# MODULE 2: The Core Aspect Type Standard
module "aspect_type_asset_governance" {
  source         = "../../custom_modules/dataplex_aspect_type"
  project_id     = var.project_id
  location       = var.location
  aspect_type_id = "vz-asset-governance"

  metadata_template = jsonencode({
    name         = "vz-asset-governance"
    type         = "record"
    recordFields = [
      { name = "owner",  type = "string", index = 1 },
      { name = "domain", type = "enum",   index = 2 },
      { name = "lifecycle", type = "enum", index = 3 }
    ]
  })
}

# MODULE 3: Data Profiling
module "profiling_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan/data-profiling"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "vz-raw-profiling-daily"
  source_bq_table  = "${local.bq_prefix}/datasets/vzdataset/tables/raw"
  results_bq_table = local.profile_results_table
  schedule_cron    = "0 0 * * *"
}

# MODULE 4: Data Quality (Manual SQL Override Mode)
module "dq_scan_raw" {
  source           = "../../custom_modules/dataplex_datascan/data-quality"
  project_id       = var.project_id
  location         = var.location
  data_scan_id     = "vz-raw-dq-daily"
  source_bq_table  = "${local.bq_prefix}/datasets/vzdataset/tables/raw"
  results_bq_table = local.dq_results_table
  
  # Manual Override Rules if needed
  dq_rules = [
    {
      name              = "id-not-null"
      dimension         = "COMPLETENESS"
      column            = "id"
      row_condition_sql = "id IS NOT NULL"
    }
  ]
}

# =============================================================================
# MODULE 5: PROFILE-BASED DQ SCANS (The Automation Engine)
# =============================================================================
data "google_client_config" "default" {}

# Fetch profile scan via REST API to resolve linked BQ table
data "http" "profile_scan_details" {
  for_each = var.dq_profile_scans
  url = "https://dataplex.googleapis.com/v1/projects/${each.value.project_id}/locations/${each.value.region}/dataScans/${each.value.existing_profile_scan_id}"
  request_headers = {
    Authorization = "Bearer ${data.google_client_config.default.access_token}"
    Accept        = "application/json"
  }
}

locals {
  profile_target_resources = {
    for key, response in data.http.profile_scan_details :
    key => jsondecode(response.response_body).data.resource
  }
}

# Fetch ALL Data Quality rule recommendations dynamically
data "google_dataplex_data_quality_rules" "recommendations" {
  for_each     = var.dq_profile_scans
  project      = each.value.project_id
  location     = each.value.region
  data_scan_id = each.value.existing_profile_scan_id
}

# Generate 50+ DQ scans automatically utilizing the recommendations
resource "google_dataplex_datascan" "dq_from_profile" {
  for_each     = var.dq_profile_scans
  project      = each.value.project_id
  location     = each.value.region
  data_scan_id = each.value.new_dq_scan_id
  
  data {
    resource = local.profile_target_resources[each.key]
  }

  data_quality_spec {
    catalog_publishing_enabled = true

    # Inject all 9 recommended rule types directly 
    dynamic "rules" {
      for_each = data.google_dataplex_data_quality_rules.recommendations[each.key].rules
      content {
        column      = rules.value.column
        dimension   = rules.value.dimension
        threshold   = rules.value.threshold
        ignore_null = rules.value.ignore_null

        dynamic "non_null_expectation"        { for_each = rules.value.non_null_expectation; content {} }
        dynamic "uniqueness_expectation"      { for_each = rules.value.uniqueness_expectation; content {} }
        dynamic "range_expectation"           { for_each = rules.value.range_expectation; content { ... } }
        dynamic "regex_expectation"           { for_each = rules.value.regex_expectation; content { ... } }
        dynamic "set_expectation"             { for_each = rules.value.set_expectation; content { ... } }
        dynamic "statistic_range_expectation" { for_each = rules.value.statistic_range_expectation; content { ... } }
        dynamic "row_condition_expectation"   { for_each = rules.value.row_condition_expectation; content { ... } }
      }
    }
  }
}
```

### 📄 3. The 9-Rule Engine Module (`custom_modules/dataplex_datascan/data-quality/main.tf`)
*This is the reusable "engine" we built under the hood. Notice the advanced 9 `dynamic` blocks that can elegantly support every possible combination of rule type without rewriting code.*

```hcl
resource "google_dataplex_datascan" "quality" {
  project      = var.project_id
  location     = var.location
  data_scan_id = var.data_scan_id

  data {
    resource = var.source_bq_table
  }

  data_quality_spec {
    sampling_percent           = var.sampling_percent
    catalog_publishing_enabled = true

    dynamic "rules" {
      for_each = var.dq_rules
      content {
        name        = rules.value.name
        dimension   = rules.value.dimension
        threshold   = lookup(rules.value, "threshold", 1.0)
        column      = lookup(rules.value, "column", null)

        dynamic "non_null_expectation" {
          for_each = lookup(rules.value, "non_null_expectation", false) ? [1] : []
          content {}
        }
        dynamic "uniqueness_expectation" {
          for_each = lookup(rules.value, "uniqueness_expectation", false) ? [1] : []
          content {}
        }
        dynamic "set_expectation" {
          for_each = lookup(rules.value, "allowed_values", null) != null ? [1] : []
          content { values = rules.value.allowed_values }
        }
        dynamic "row_condition_expectation" {
          for_each = lookup(rules.value, "row_condition_sql", null) != null ? [1] : []
          content { sql_expression = rules.value.row_condition_sql }
        }
        # ... (and 5 more advanced statistical/SQL assertion dynamic blocks)
      }
    }

    post_scan_actions {
      bigquery_export {
        results_table = var.results_bq_table
      }
    }
  }
}
```
