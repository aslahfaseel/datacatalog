variable "project_id" {
  type = string
}

variable "location" {
  type    = string
  default = "us-central1"
}

variable "data_scan_id" {
  type = string
}

variable "display_name" {
  type = string
}

variable "description" {
  type    = string
  default = ""
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "source_bq_table" {
  type = string
}

variable "results_bq_table" {
  type = string
}

variable "scan_type" {
  type = string
  validation {
    condition     = contains(["profiling", "quality"], var.scan_type)
    error_message = "scan_type must be 'profiling' or 'quality'."
  }
}

variable "schedule_cron" {
  type    = string
  default = null
}

variable "sampling_percent" {
  type    = number
  default = 100.0
}

variable "row_filter" {
  type    = string
  default = null
}

variable "incremental_field" {
  type    = string
  default = null
}

variable "alert_emails" {
  type    = list(string)
  default = []
}

variable "dq_rules" {
  type = list(object({
    name              = string
    dimension         = string
    threshold         = optional(number, 1.0)
    description       = optional(string, "")
    column            = optional(string, null)
    row_condition_sql = optional(string, null)
    sql_assertion     = optional(string, null)
  }))
  default = []
}
