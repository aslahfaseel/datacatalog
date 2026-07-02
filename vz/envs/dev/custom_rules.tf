locals {
  # Custom SQL-based rules — uses your own SQL expressions.
  # Engineers add entries here; developers reference them by key in tables_to_scan.csv.
  custom_rules = {

    # COMPLETENESS: Table-level aggregate checks
    "raw-table-has-data" = {
      name                = "raw-table-has-data"
      dimension           = "COMPLETENESS"
      table_condition_sql = "COUNT(*) > 0"
    }
    "minimum-1000-rows" = {
      name                = "minimum-1000-rows"
      dimension           = "COMPLETENESS"
      table_condition_sql = "COUNT(*) >= 1000"
    }

    # COMPLETENESS: Row-level null checks (custom SQL style)
    "id-not-null" = {
      name              = "id-not-null"
      dimension         = "COMPLETENESS"
      column            = "id"
      row_condition_sql = "id IS NOT NULL"
    }

    # CONSISTENCY: Cross-column checks per row
    "end-date-after-start" = {
      name              = "end-date-after-start"
      dimension         = "CONSISTENCY"
      row_condition_sql = "end_date > start_date"
    }
    "discount-less-than-price" = {
      name              = "discount-less-than-price"
      dimension         = "CONSISTENCY"
      row_condition_sql = "discount_amount <= unit_price"
    }

    # TIMELINESS: Freshness checks
    "no-future-created-date" = {
      name              = "no-future-created-date"
      dimension         = "TIMELINESS"
      row_condition_sql = "created_at <= CURRENT_TIMESTAMP()"
    }
    "data-freshness-daily" = {
      name              = "data-freshness-daily"
      dimension         = "TIMELINESS"
      row_condition_sql = "DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 DAY)"
    }

    # VALIDITY: Value checks
    "amount-positive" = {
      name              = "amount-positive"
      dimension         = "VALIDITY"
      column            = "amount"
      row_condition_sql = "amount > 0"
    }
  }
}
