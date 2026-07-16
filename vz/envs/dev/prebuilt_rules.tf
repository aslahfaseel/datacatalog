locals {
  # Prebuilt Dataplex native rule types — no custom SQL required.
  # Engineers add entries here; developers reference them by key in tables_to_scan.csv.
  prebuilt_rules = {

    # COMPLETENESS: Non-null checks
    "customer-id-not-null" = {
      name                 = "customer-id-not-null"
      dimension            = "COMPLETENESS"
      column               = "customer_id"
      non_null_expectation = true
      threshold            = 1.0
    }
    "email-not-null" = {
      name                 = "email-not-null"
      dimension            = "COMPLETENESS"
      column               = "email"
      non_null_expectation = true
      threshold            = 0.95
    }

    # UNIQUENESS: Duplicate checks
    "customer-id-unique" = {
      name                   = "customer-id-unique"
      dimension              = "UNIQUENESS"
      column                 = "customer_id"
      uniqueness_expectation = true
      threshold              = 1.0
    }
    "order-id-unique" = {
      name                   = "order-id-unique"
      dimension              = "UNIQUENESS"
      column                 = "order_id"
      uniqueness_expectation = true
      threshold              = 1.0
    }

    # VALIDITY: Range checks
    "age-valid-range" = {
      name      = "age-valid-range"
      dimension = "VALIDITY"
      column    = "age"
      threshold = 1.0
      range_expectation = {
        min_value          = "18"
        max_value          = "120"
        strict_min_enabled = false
        strict_max_enabled = false
      }
    }
    "revenue-non-negative" = {
      name      = "revenue-non-negative"
      dimension = "VALIDITY"
      column    = "revenue"
      threshold = 1.0
      range_expectation = {
        min_value          = "0"
        max_value          = null
        strict_min_enabled = false
        strict_max_enabled = false
      }
    }

    # VALIDITY: Set/enum checks
    "order-status-valid" = {
      name           = "order-status-valid"
      dimension      = "VALIDITY"
      column         = "status"
      threshold      = 1.0
      allowed_values = ["PENDING", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]
    }

    # VALIDITY: Regex format checks
    "email-format-valid" = {
      name      = "email-format-valid"
      dimension = "VALIDITY"
      column    = "email"
      threshold = 0.99
      regex     = "^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}$"
    }
  }
}
