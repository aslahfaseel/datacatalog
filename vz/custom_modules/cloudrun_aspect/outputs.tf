output "job_name" {
  description = "The name of the deployed Cloud Run Job."
  value       = google_cloud_run_v2_job.aspect_patcher.name
}

output "job_uri" {
  description = "The full resource URI of the Cloud Run Job."
  value       = google_cloud_run_v2_job.aspect_patcher.id
}
