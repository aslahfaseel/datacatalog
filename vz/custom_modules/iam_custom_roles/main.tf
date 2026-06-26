######################################################################
# MODULE: iam_custom_roles
# PURPOSE: Creates least-privilege custom IAM roles for the VZ
#          Data Governance pipeline service account.
#
# IMPORTANT: This module must be applied by a user/SA that has the
#            roles/iam.roleAdmin or roles/owner role on the project.
#            The vz-datacatalog SA does NOT have this permission.
#
# USAGE: Apply this once with a privileged account, then the
#        dataplex_iam module can bind the service account to the role.
######################################################################

# -----------------------------------------------------------------------
# Custom Role: policyTagStamper
# Replaces: roles/bigquery.admin (too broad)
#
# Why each permission:
#   bigquery.tables.get    → Read the current BQ table schema before patching
#   bigquery.tables.update → Write back the updated schema with Policy Tag IDs
#   bigquery.tables.setCategory → Attach the physical Policy Tag to the column
#                                 (this is the key permission missing from dataEditor)
# -----------------------------------------------------------------------
resource "google_project_iam_custom_role" "policy_tag_stamper" {
  project     = var.project_id
  role_id     = "policyTagStamper"
  title       = "Policy Tag Stamper"
  description = "Minimal permissions to allow automated Cloud Run job to attach BigQuery column-level Policy Tags. Replaces roles/bigquery.admin."

  permissions = [
    "bigquery.tables.get",
    "bigquery.tables.update",
    "bigquery.tables.setCategory",
  ]
}
