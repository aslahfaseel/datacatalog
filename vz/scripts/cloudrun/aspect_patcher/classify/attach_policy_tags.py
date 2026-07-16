from google.cloud import bigquery
import logging

def attach_policy_tags(
    governance_project: str,
    curated_project: str,
    target_project_id: str,
    recommended_table: str,
    mapping_table: str,
    dataset_id: str,
    table_id: str
) -> tuple:
    """
    Function 4: Attaches physical BigQuery Policy Tags based on recommendations and reference mappings.
    """
    bq_client = bigquery.Client(project=curated_project)
    target_table_full = f"{target_project_id}.{dataset_id}.{table_id}"

    try:
        # 1. Fetch correct policy tags from infotype_mapping_local reference
        query_map = f"SELECT data_classification, policy_tag_id FROM `{mapping_table}`"
        mapping_rows = bq_client.query(query_map).result()
        tag_map = {row.data_classification: row.policy_tag_id for row in mapping_rows}

        # 2. Read calculated columns from recommended_classification
        query_recs = f"""
            SELECT column_id, dlp_classification 
            FROM `{recommended_table}`
            WHERE project_id = '{target_project_id}' AND dataset_id = '{dataset_id}' AND table_id = '{table_id}'
        """
        rec_rows = bq_client.query(query_recs).result()
        
        column_tag_assignments = {}
        for row in rec_rows:
            classification = row.dlp_classification
            if classification in tag_map:
                column_tag_assignments[row.column_id] = tag_map[classification]

        if not column_tag_assignments:
            logging.info(f"No columns identified requiring policy tags for {table_id}.")
            return 0, 0

        # 3. Update BigQuery schema
        table = bq_client.get_table(target_table_full)
        new_schema = []
        updated_columns_count = 0

        for field in table.schema:
            if field.name in column_tag_assignments:
                updated_columns_count += 1
                new_field = bigquery.SchemaField(
                    name=field.name,
                    field_type=field.field_type,
                    mode=field.mode,
                    description=field.description,
                    policy_tags=bigquery.PolicyTagList(names=[column_tag_assignments[field.name]])
                )
                new_schema.append(new_field)
            else:
                new_schema.append(field)

        table.schema = new_schema
        bq_client.update_table(table, ["schema"])

        logging.info(f"Policy Tag Sync Complete: {updated_columns_count} columns updated for {table_id}.")
        return updated_columns_count, 1

    except Exception as e:
        logging.error(f"Error attaching policy tags for {table_id}: {str(e)}", exc_info=True)
        raise e

if __name__ == "__main__":
    # Example standalone execution for testing
    logging.basicConfig(level=logging.INFO)
    attach_policy_tags(
        governance_project="central-data-governance-469014",
        curated_project="curated-zone-495715",
        target_project_id="curated-zone-495715",
        recommended_table="curated-zone-495715.data_classification_demo.recommended_classification",
        mapping_table="curated-zone-495715.data_classification_demo.infotype_mapping_local",
        dataset_id="data_classification_demo",
        table_id="corporate_hr_employees"
    )
