variable "project_id" {
  type = string
}

variable "terraform_sa" {
  type = string
}

variable "dataplex_service_agent" {
  type = string
}

# When the security team creates the policyTagStamper custom role via
# custom_modules/iam_custom_roles, set this to the output role ID.
# Format: "projects/PROJECT_ID/roles/policyTagStamper"
# Leaving it empty keeps the temporary roles/bigquery.admin active.
variable "custom_policy_tag_stamper_role_id" {
  type        = string
  description = "ID of the policyTagStamper custom IAM role created by the security team. Leave empty to use roles/bigquery.admin temporarily."
  default     = ""
}
