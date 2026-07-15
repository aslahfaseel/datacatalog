from google.cloud import dataplex_v1
from google.protobuf import field_mask_pb2
from google.cloud import bigquery
from google.api_core import exceptions
import logging

def update_dataplex_aspects(
    governance_project: str,
    target_project_id: str,
    curated_project: str,
    location: str,
    recommended_table: str,
    dataset_id: str,
    table_id: str
) -> int:
    """
    Function 3: Reads recommendations from BigQuery and updates Dataplex column aspects (Universal Catalog).
    """
    # Using the global endpoint is recommended for 'lookup_entry' as routing 
    # is handled by the 'name' field in the request.
    catalog_client = dataplex_v1.CatalogServiceClient(
        client_options={"api_endpoint": "dataplex.googleapis.com"}
    )
    bq_client = bigquery.Client(project=curated_project)

    bq_resource = f"bigquery.googleapis.com/projects/{target_project_id}/datasets/{dataset_id}/tables/{table_id}"
    
    # Use the shortened format required by the Aspects map
    class_aspect_type = f"{governance_project}.{location}.data-classification"
    
    # For Universal Catalog lookups of BigQuery resources, the scope must be the project 
    # where the BigQuery dataset resides. Use the 'global' location for the lookup call.
    lookup_scope = f"projects/{target_project_id}/locations/global"

    try:
        # 1. Read recommendations from staging table
        query = f"""
            SELECT column_id, dlp_classification 
            FROM `{recommended_table}`
            WHERE project_id = '{target_project_id}' 
            AND dataset_id = '{dataset_id}' 
            AND table_id = '{table_id}'
        """
        rows = bq_client.query(query).result()
        recommendation_map = {row.column_id: row.dlp_classification for row in rows}

        if not recommendation_map:
            logging.warning(f"No recommendations found in BigQuery for {table_id}. Skipping Dataplex sync.")
            return 0

        # 2. Lookup the Dataplex Entry (Target Project Catalog)
        logging.info(f"Looking up Dataplex Entry for {table_id}...")
        try:
            # Attempt lookup by full resource name (standard method)
            entry = catalog_client.lookup_entry(request={
                "name": lookup_scope,
                "entry": f"//{bq_resource}"
            })
        except (exceptions.NotFound, exceptions.InvalidArgument) as e:
            try:
                # Attempt lookup without the // prefix
                entry = catalog_client.lookup_entry(request={
                    "name": lookup_scope,
                    "entry": bq_resource
                })
            except Exception:
                # Final fallback: construct deterministic system-managed entry name in the regional scope
                entry_name = f"projects/{target_project_id}/locations/{location}/entryGroups/@bigquery/entries/{bq_resource}"
                logging.info(f"Lookup failed. Attempting direct GetEntry in native region: {entry_name}")
                entry = catalog_client.get_entry(name=entry_name)

        # Filter out system-managed aspects (like bigquery-policy) that we don't have 
        # permissions to re-attach, to avoid 403 errors during update.
        # Also remove existing data-classification aspects to prevent "duplicate aspect" errors
        # if the existing keys use a different format (e.g. project number vs project ID).
        aspects_to_update = {
            k: v for k, v in entry.aspects.items() 
            if "655216118709" not in k 
            and "data-classification" not in k
            and "vz-asset-governance" not in k
        }
        updated_count = 0

        # 3. Construct column aspects
        for col_name, classification in recommendation_map.items():
            # Skip if classification is None or empty to avoid JsonNull errors in Dataplex
            if not classification:
                continue
            updated_count += 1
            # Correct format for column aspects in Universal Catalog is aspect_type@Schema.column_name
            aspect_key = f"{class_aspect_type}@Schema.{col_name}"
            aspects_to_update[aspect_key] = dataplex_v1.Aspect(
                data={"data-classification": classification}
            )

        # 4. Save to Dataplex
        if updated_count > 0:
            updated_entry = dataplex_v1.Entry(name=entry.name, aspects=aspects_to_update)
            catalog_client.update_entry(
                entry=updated_entry, 
                update_mask=field_mask_pb2.FieldMask(paths=["aspects"])
            )

        logging.info(f"Dataplex Aspect Sync Complete: {updated_count} column(s) updated for {table_id}.")
        return updated_count

    except Exception as e:
        logging.error(f"Error updating Dataplex aspects for {table_id}: {str(e)}", exc_info=True)
        raise e

if __name__ == "__main__":
    # Example standalone execution for testing
    update_dataplex_aspects(
        governance_project="central-data-governance-469014",
        target_project_id="curated-zone-495715",
        curated_project="curated-zone-495715",
        location="us-central1",
        recommended_table="curated-zone-495715.data_classification_demo.recommended_classification",
        dataset_id="data_classification_demo",
        table_id="corporate_hr_employees"
    )
