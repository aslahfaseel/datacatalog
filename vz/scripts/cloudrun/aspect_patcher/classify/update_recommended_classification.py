from google.cloud import bigquery
import logging

logging.basicConfig(level=logging.INFO)

def update_recommended_classification(
    governance_project: str, # ADDED: Need the governance project for the scan parent
    curated_project: str,
    target_project_id: str,
    location: str,
    dataset_id: str,
    table_id: str,
    mapping_table: str,
    recommended_table: str,
    dlp_results_table: str
) -> int:
    """
    Function 2: Reads DLP profile, maps against infotype_mapping_local, 
    and logs recommendations to a staging BigQuery table.
    """
    bq_client = bigquery.Client(project=governance_project)

    # This SQL replaces the Python logic with a set-based aggregation in BigQuery.
    # It follows the specific aggregation and priority logic requested in your input.
    query = f"""
    CREATE OR REPLACE TABLE `{recommended_table}` AS
WITH
LATEST_TABLE_PROFILE AS (
    SELECT
        table_profile.table_id,
        MAX(table_profile.profile_last_generated.timestamp) AS latest_profile_time
    FROM
        `{dlp_results_table}`
    GROUP BY
        table_profile.table_id
),
ALL_DATA AS (
    SELECT
        column_profile.dataset_project_id,
        column_profile.dataset_id,
        column_profile.table_id,
        column_profile.column,
        column_profile.data_risk_level.score AS risk_score,
        column_profile.column_info_type.info_type.name AS primary_infotype,
        column_profile.sensitivity_score.score AS primary_sensitivity_score,
        om.info_type.name AS secondary_infotype,
        om.info_type.sensitivity_score.score AS secondary_sensitivity_score,
        om.estimated_prevalence,
        ddr.column_profile.profile_last_generated.timestamp AS scan_date
    FROM
        `{dlp_results_table}` ddr
    LEFT JOIN
        UNNEST(column_profile.other_matches) AS om
    INNER JOIN
        LATEST_TABLE_PROFILE latest
    ON
        ddr.column_profile.table_id = latest.table_id
        AND ddr.column_profile.profile_last_generated.timestamp = latest.latest_profile_time
        AND ddr.column_profile.dataset_project_id IS NOT NULL
),
FINAL_DATA AS (
    SELECT
        scan_date,
        dataset_project_id,
        dataset_id,
        table_id,
        COLUMN,
        risk_score,
        suggested_sensitivity_score,
        ARRAY_AGG(STRUCT(info_type as info_code, type,
            im.data_classification as classification,
            sensitivity_score, estimated_prevalence
            ) ORDER BY type DESC, estimated_prevalence DESC ) AS matches,
        MIN(CASE 
            WHEN type='Primary' AND im.data_classification= 'Confidential' THEN 1 
            WHEN type='Primary' AND im.data_classification= 'Internal' THEN 2 
            WHEN type='Primary' AND im.data_classification= 'Public' THEN 3
            WHEN type='Other' AND im.data_classification= 'Confidential' THEN 4
            WHEN type='Other' AND im.data_classification= 'Internal' THEN 5
            WHEN type='Other' AND im.data_classification= 'Public' THEN 6 END
        ) AS priority
    FROM (
        SELECT DISTINCT
            dataset_project_id,
            dataset_id,
            table_id,
            COLUMN,
            risk_score,
            suggested_sensitivity_score,
            info_type AS info_type,
            sensitivity_score AS sensitivity_score,
            estimated_prevalence,
            type,
            scan_date,
            MAX(CASE WHEN info_type IS NULL THEN 0 ELSE 1 END) OVER(PARTITION BY dataset_project_id, dataset_id, table_id, COLUMN) AS flags
        FROM (
            SELECT
                dataset_project_id, dataset_id, table_id, COLUMN, risk_score,
                primary_sensitivity_score AS suggested_sensitivity_score,
                primary_infotype AS info_type,
                primary_sensitivity_score AS sensitivity_score,
                NULL as estimated_prevalence,
                'Primary' as type,
                scan_date
            FROM ALL_DATA
            UNION ALL
            SELECT
                dataset_project_id, dataset_id, table_id, COLUMN, risk_score,
                primary_sensitivity_score AS suggested_sensitivity_score,
                secondary_infotype AS info_type,
                secondary_sensitivity_score AS sensitivity_score,
                estimated_prevalence,
                'Other' as type,
                scan_date
            FROM ALL_DATA
            WHERE (estimated_prevalence is null or estimated_prevalence>=50)
        )
        WHERE (info_type IS NOT NULL OR sensitivity_score IS NOT NULL)
    ) tbl
    LEFT JOIN
        `{mapping_table}` im
    ON
        tbl.info_type = im.infotype
    WHERE
        (info_type IS NOT NULL AND flags=1)
        OR (info_type IS NULL AND flags=0)
    GROUP BY
        dataset_project_id, dataset_id, table_id, COLUMN, risk_score, suggested_sensitivity_score, scan_date 
)
SELECT
    
    ddr.dataset_project_id as project_id,
    ddr.dataset_id,
    ddr.table_id,
    ddr.column as column_id,
    ddr.risk_score AS dlp_risk,
    CASE  
        WHEN ddr.priority IN (1,4) THEN 'Confidential'
        WHEN ddr.priority IN (2,5) THEN 'Internal' 
        WHEN ddr.priority IN (3,6) THEN 'Public' 
        ELSE NULL 
    END dlp_classification,
    ddr.scan_date AS dlp_scan_date,
    ddr.matches
FROM
    FINAL_DATA ddr
    """

    try:
        print(f"DEBUG: Starting SQL execution for table: {table_id}")
        logging.info(f"Running aggregation query to update {recommended_table} for {table_id}...")
        query_job = bq_client.query(query)
        query_job.result()
        print(f"DEBUG: SQL execution finished for table: {table_id}")

        # Return the count of rows updated for the current table context
        result_table = bq_client.get_table(recommended_table)
        count = result_table.num_rows
        logging.info(f"Analysis Complete: Mapped {count} column(s) successfully.")
        print(f"DEBUG: update_recommended_classification fully completed for table: {table_id}")
        return count
    except Exception as e:
        logging.error(f"Error executing classification aggregation SQL: {str(e)}", exc_info=True)
        raise e
