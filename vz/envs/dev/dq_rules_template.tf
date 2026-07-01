locals {
  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 1: non_null_expectation
  # Checks that a column has NO null values.
  # Set threshold < 1.0 to allow a % of nulls (e.g. 0.95 = max 5% nulls).
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_non_null = [
    {
      name                 = "customer-id-not-null"
      description          = "Customer ID must never be null"
      dimension            = "COMPLETENESS"
      column               = "customer_id"
      threshold            = 1.0
      non_null_expectation = true
    },
    {
      name                 = "email-not-null"
      description          = "Email must be present in at least 95% of rows"
      dimension            = "COMPLETENESS"
      column               = "email"
      threshold            = 0.95          # allows up to 5% nulls
      non_null_expectation = true
    },
    {
      name                 = "phone-not-null"
      description          = "Phone number completeness check"
      dimension            = "COMPLETENESS"
      column               = "phone_number"
      threshold            = 0.90
      non_null_expectation = true
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 2: uniqueness_expectation
  # Checks that a column has NO duplicate values.
  # Best for primary keys, email addresses, account numbers.
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_uniqueness = [
    {
      name                    = "customer-id-unique"
      description             = "Customer ID must be a unique primary key"
      dimension               = "UNIQUENESS"
      column                  = "customer_id"
      threshold               = 1.0
      uniqueness_expectation  = true
    },
    {
      name                    = "order-id-unique"
      description             = "Order ID must be unique across all rows"
      dimension               = "UNIQUENESS"
      column                  = "order_id"
      threshold               = 1.0
      uniqueness_expectation  = true
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 3: range_expectation
  # Checks that numeric or date column values fall within a defined range.
  # min_value / max_value can be null to leave one side open-ended.
  # strict_min_enabled = true means value must be GREATER THAN (not >=).
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_range = [
    {
      name        = "age-valid-range"
      description = "Age must be between 18 and 120"
      dimension   = "VALIDITY"
      column      = "age"
      threshold   = 1.0
      range_expectation = {
        min_value          = "18"
        max_value          = "120"
        strict_min_enabled = false
        strict_max_enabled = false
      }
    },
    {
      name        = "revenue-non-negative"
      description = "Revenue cannot be negative"
      dimension   = "VALIDITY"
      column      = "revenue"
      threshold   = 1.0
      range_expectation = {
        min_value          = "0"
        max_value          = null  # no upper bound
        strict_min_enabled = false
        strict_max_enabled = false
      }
    },
    {
      name        = "credit-score-range"
      description = "Credit score must be between 300 and 850"
      dimension   = "ACCURACY"
      column      = "credit_score"
      threshold   = 0.99
      range_expectation = {
        min_value          = "300"
        max_value          = "850"
        strict_min_enabled = false
        strict_max_enabled = false
      }
    },
    {
      name        = "discount-percent-range"
      description = "Discount percentage must be strictly between 0 and 100 (exclusive)"
      dimension   = "VALIDITY"
      column      = "discount_pct"
      threshold   = 1.0
      range_expectation = {
        min_value          = "0"
        max_value          = "100"
        strict_min_enabled = true  # value > 0 (not >= 0)
        strict_max_enabled = true  # value < 100 (not <= 100)
      }
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 4: regex_expectation
  # Checks that column values match a regular expression pattern.
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_regex = [
    {
      name        = "email-format-valid"
      description = "Email must be a valid email format"
      dimension   = "VALIDITY"
      column      = "email"
      threshold   = 0.99
      regex       = "^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}$"
    },
    {
      name        = "phone-us-format"
      description = "Phone must be a valid 10-digit US number"
      dimension   = "VALIDITY"
      column      = "phone_number"
      threshold   = 0.95
      regex       = "^\\+?1?[0-9]{10}$"
    },
    {
      name        = "zip-code-format"
      description = "ZIP code must be 5 digits (US format)"
      dimension   = "VALIDITY"
      column      = "zip_code"
      threshold   = 0.99
      regex       = "^[0-9]{5}(-[0-9]{4})?$"
    },
    {
      name        = "ssn-format"
      description = "SSN must match XXX-XX-XXXX format"
      dimension   = "VALIDITY"
      column      = "ssn"
      threshold   = 1.0
      regex       = "^[0-9]{3}-[0-9]{2}-[0-9]{4}$"
    },
    {
      name        = "credit-card-format"
      description = "Credit card must be 13-19 digits"
      dimension   = "VALIDITY"
      column      = "credit_card_number"
      threshold   = 1.0
      regex       = "^[0-9]{13,19}$"
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 5: set_expectation
  # Checks that a column's values are only from a predefined set.
  # Best for status fields, categories, country codes, etc.
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_set = [
    {
      name           = "order-status-valid"
      description    = "Order status must be one of the defined states"
      dimension      = "VALIDITY"
      column         = "status"
      threshold      = 1.0
      allowed_values = ["PENDING", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]
    },
    {
      name           = "country-code-valid"
      description    = "Country code must be a known ISO 2-letter code (sample set)"
      dimension      = "VALIDITY"
      column         = "country_code"
      threshold      = 0.99
      allowed_values = ["US", "GB", "CA", "AU", "DE", "FR", "IN", "JP"]
    },
    {
      name           = "data-classification-valid"
      description    = "Classification label must be from approved taxonomy"
      dimension      = "VALIDITY"
      column         = "data_classification"
      threshold      = 1.0
      allowed_values = ["Public", "Internal", "Confidential", "Restricted"]
    },
    {
      name           = "payment-method-valid"
      description    = "Payment method must be known"
      dimension      = "VALIDITY"
      column         = "payment_method"
      threshold      = 1.0
      allowed_values = ["CREDIT_CARD", "DEBIT_CARD", "WIRE_TRANSFER", "PAYPAL", "CRYPTO"]
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 6: statistic_range_expectation
  # Checks that a column's statistical measure (MEAN / MIN / MAX) falls
  # within an expected range. Useful for anomaly detection at the table level.
  # statistic options: MEAN, MIN, MAX
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_statistic_range = [
    {
      name        = "order-value-avg-in-range"
      description = "Average order value should be between $20 and $500"
      dimension   = "ACCURACY"
      column      = "order_value"
      threshold   = 1.0
      statistic_range_expectation = {
        statistic          = "MEAN"
        min_value          = "20"
        max_value          = "500"
        strict_min_enabled = false
        strict_max_enabled = false
      }
    },
    {
      name        = "transaction-amount-max-check"
      description = "Maximum transaction amount should never exceed $1,000,000"
      dimension   = "ACCURACY"
      column      = "transaction_amount"
      threshold   = 1.0
      statistic_range_expectation = {
        statistic          = "MAX"
        min_value          = null
        max_value          = "1000000"
        strict_min_enabled = false
        strict_max_enabled = false
      }
    },
    {
      name        = "rating-avg-range"
      description = "Average customer rating must be between 1.0 and 5.0"
      dimension   = "ACCURACY"
      column      = "rating"
      threshold   = 1.0
      statistic_range_expectation = {
        statistic          = "MEAN"
        min_value          = "1.0"
        max_value          = "5.0"
        strict_min_enabled = false
        strict_max_enabled = false
      }
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 7: row_condition_expectation
  # Evaluates a custom SQL expression on EACH ROW independently.
  # Use for cross-column relationships or complex business logic.
  # The expression must return TRUE for the row to PASS.
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_row_condition = [
    {
      name              = "end-date-after-start"
      description       = "End date must be after start date on every row"
      dimension         = "CONSISTENCY"
      threshold         = 1.0
      row_condition_sql = "end_date > start_date"
    },
    {
      name              = "discount-less-than-price"
      description       = "Discount amount cannot exceed the item price"
      dimension         = "CONSISTENCY"
      threshold         = 1.0
      row_condition_sql = "discount_amount <= unit_price"
    },
    {
      name              = "shipped-date-only-if-delivered"
      description       = "Shipped date must be set when status is DELIVERED"
      dimension         = "CONSISTENCY"
      threshold         = 1.0
      row_condition_sql = "NOT (status = 'DELIVERED' AND shipped_date IS NULL)"
    },
    {
      name              = "no-future-created-date"
      description       = "Record creation date cannot be in the future"
      dimension         = "TIMELINESS"
      threshold         = 1.0
      row_condition_sql = "created_at <= CURRENT_TIMESTAMP()"
    },
    {
      name              = "data-freshness-daily"
      description       = "Records must have been created within the last 2 days"
      dimension         = "TIMELINESS"
      threshold         = 0.90
      row_condition_sql = "DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 DAY)"
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 8: table_condition_expectation
  # Evaluates a SQL expression over the WHOLE TABLE (aggregate check).
  # Returns a single true/false result — not per-row.
  # Use for row count checks, referential integrity, etc.
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_table_condition = [
    {
      name                 = "table-not-empty"
      description          = "Table must have at least 1 row"
      dimension            = "COMPLETENESS"
      table_condition_sql  = "COUNT(*) > 0"
    },
    {
      name                 = "minimum-row-count"
      description          = "Table must have at least 1000 rows (sanity volume check)"
      dimension            = "COMPLETENESS"
      table_condition_sql  = "COUNT(*) >= 1000"
    },
    {
      name                 = "debit-credit-balanced"
      description          = "Sum of debit entries must equal sum of credit entries"
      dimension            = "CONSISTENCY"
      table_condition_sql  = "ABS(SUM(IF(type='DEBIT', amount, 0)) - SUM(IF(type='CREDIT', amount, 0))) < 0.01"
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # RULE TYPE 9: sql_assertion
  # Runs a full SQL query. The rule PASSES if the query returns 0 rows.
  # Any row returned is treated as a VIOLATION.
  # Most flexible rule — can join external reference tables.
  # ─────────────────────────────────────────────────────────────────────────
  dq_rules_sql_assertion = [
    {
      name          = "no-orphan-orders"
      description   = "Every order must have a valid customer in the customers table"
      dimension     = "CONSISTENCY"
      sql_assertion = <<-SQL
        SELECT o.order_id
        FROM `dmgcp-del-181.vzdataset.raw_order` o
        LEFT JOIN `dmgcp-del-181.vzdataset.raw_customer` c ON o.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
      SQL
    },
    {
      name          = "no-duplicate-transactions"
      description   = "No two rows should share same transaction_id and amount on same day"
      dimension     = "UNIQUENESS"
      sql_assertion = <<-SQL
        SELECT transaction_id, transaction_date, amount, COUNT(*) as cnt
        FROM `dmgcp-del-181.vzdataset.raw`
        GROUP BY transaction_id, transaction_date, amount
        HAVING cnt > 1
      SQL
    },
  ]

  # ─────────────────────────────────────────────────────────────────────────
  # COMBINED RULE SET — merge all rules into one list for a scan
  # Uncomment and use in your module call:
  #   dq_rules = local.all_dq_rules_raw_customer
  # ─────────────────────────────────────────────────────────────────────────
  all_dq_rules_raw_customer = concat(
    local.dq_rules_non_null,
    local.dq_rules_uniqueness,
    local.dq_rules_range,
    local.dq_rules_regex,
    local.dq_rules_set,
    local.dq_rules_statistic_range,
    local.dq_rules_row_condition,
    local.dq_rules_table_condition,
    local.dq_rules_sql_assertion,
  )
}
