output "policy_tag_stamper_role_id" {
  description = "The full ID of the policyTagStamper custom role. Use this to bind the role to a service account in dataplex_iam."
  value       = google_project_iam_custom_role.policy_tag_stamper.id
}
