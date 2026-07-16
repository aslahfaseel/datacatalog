#!/bin/bash
# =============================================================================
# run_pipeline.sh — Full Automated Dataplex Governance Pipeline
# =============================================================================
# Usage:
#   chmod +x run_pipeline.sh
#   ./run_pipeline.sh
#
# What this does:
#   Step 1: Upload CSVs + Deploy Profiling & Custom DQ Scans (Terraform)
#   Step 2: Force-Run the Data Profile Scans via gcloud API
#   Step 3: Poll until ALL Profile Scans have SUCCEEDED
#   Step 4: Upload the filled profile_based_dq.csv + Deploy DQ Rules Scans (Terraform)
# =============================================================================

set -e

# ── Config ────────────────────────────────────────────────────────────────────
GCS_BUCKET="vz-datacatalog"
PROJECT_ID="dmgcp-del-181"
LOCATION="us-central1"
POLL_INTERVAL_SECS=30

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TABLES_CSV="$SCRIPT_DIR/profiling.csv"
CUSTOM_DQ_CSV="$SCRIPT_DIR/custom_dq.csv"
PROFILE_DQ_CSV="$SCRIPT_DIR/profile_based_dq.csv"
EMPTY_PROFILE_DQ_CSV="$SCRIPT_DIR/empty_profile_based_dq.csv"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

# ── Step 1: Upload CSVs + Terraform Apply (Profiling + Custom DQ only) ────────
log "════════════════════════════════════════════════════"
log "STEP 1 — Uploading CSVs and deploying initial scans"
log "════════════════════════════════════════════════════"

# Start with an EMPTY profile_based_dq so Terraform doesn't try to read
# Dataplex recommendations before the profile has run.
echo "project_id,dataset,table" > "$EMPTY_PROFILE_DQ_CSV"

log "Uploading profiling.csv to gs://$GCS_BUCKET/data/"
gsutil cp "$TABLES_CSV" "gs://$GCS_BUCKET/data/profiling.csv"

log "Uploading custom_dq.csv to gs://$GCS_BUCKET/data/"
gsutil cp "$CUSTOM_DQ_CSV" "gs://$GCS_BUCKET/data/custom_dq.csv"

log "Uploading empty profile_based_dq.csv to gs://$GCS_BUCKET/data/"
gsutil cp "$EMPTY_PROFILE_DQ_CSV" "gs://$GCS_BUCKET/data/profile_based_dq.csv"

log "Running terraform apply for profiling and custom DQ scans..."
terraform apply \
  -target=module.profiling_scan \
  -target=module.dq_scan \
  -auto-approve

# ── Step 2: Force-Run ALL Profile Scans ──────────────────────────────────────
log "════════════════════════════════════════════════════"
log "STEP 2 — Force-running all Data Profile scans"
log "════════════════════════════════════════════════════"

# Read each table from the CSV (skip the header row)
SCAN_IDS=()
while IFS=',' read -r project_id table_key dataset table dq_rules; do
  [[ "$project_id" == "project_id" ]] && continue  # skip header
  
  # Strip hidden Windows \r carriage returns from the end of the line
  table="${table//$'\r'/}"
  
  SCAN_ID="${dataset//_/-}-${table//_/-}-data-profile-scan"
  log "Triggering profile scan: $SCAN_ID"
  gcloud dataplex datascans run "$SCAN_ID" \
    --project="$project_id" \
    --location="$LOCATION"
  SCAN_IDS+=("$SCAN_ID:$project_id")
done < "$TABLES_CSV"

# ── Step 3: Poll Until ALL Profile Scans Have Succeeded ───────────────────────
log "════════════════════════════════════════════════════"
log "STEP 3 — Polling profile scans until all SUCCEED"
log "════════════════════════════════════════════════════"

for ENTRY in "${SCAN_IDS[@]}"; do
  SCAN_ID="${ENTRY%%:*}"
  PROJ_ID="${ENTRY##*:}"
  log "Waiting for scan '$SCAN_ID' to complete..."

  while true; do
    STATUS=$(gcloud dataplex datascans jobs list \
      --datascan="$SCAN_ID" \
      --project="$PROJ_ID" \
      --location="$LOCATION" \
      --format="value(state)" \
      --sort-by="~createTime" \
      --limit=1 2>/dev/null || echo "UNKNOWN")

    log "  → $SCAN_ID status: $STATUS"

    if [[ "$STATUS" == "SUCCEEDED" ]]; then
      log "  ✅ $SCAN_ID succeeded!"
      break
    elif [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then
      fail "Scan '$SCAN_ID' ended with status: $STATUS. Aborting pipeline."
    fi

    sleep "$POLL_INTERVAL_SECS"
  done
done

# ── Step 4: Upload Filled CSV + Deploy Profile-Based DQ Scans ─────────────────
log "════════════════════════════════════════════════════"
log "STEP 4 — Uploading profile_based_dq.csv and deploying DQ rules scans"
log "════════════════════════════════════════════════════"

log "Uploading filled profile_based_dq.csv to gs://$GCS_BUCKET/data/"
gsutil cp "$PROFILE_DQ_CSV" "gs://$GCS_BUCKET/data/profile_based_dq.csv"

log "Running terraform apply for profile-based DQ scans..."
terraform apply -auto-approve

log "════════════════════════════════════════════════════"
log "✅ Pipeline complete! All 3 scans are now active:"
log "   • Data Profile Scan"
log "   • Custom Data Quality Scan"
log "   • Profile-Based DQ Rules Scan"
log "════════════════════════════════════════════════════"
