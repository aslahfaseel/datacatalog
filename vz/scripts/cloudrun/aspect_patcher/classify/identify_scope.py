import yaml
import os
import sys
from google.cloud import bigquery

def identify_scope(config_yaml_path: str) -> list:
    """
    Function 1: Reads a YAML configuration of inscope datasets and tables.
    Returns a list of structured table coordinates to process.
    If dataset or tables are omitted, it discovers them using the BigQuery API.
    """
    try:
        client = bigquery.Client()
        with open(config_yaml_path, 'r') as file:
            config = yaml.safe_load(file) or {}
        
        inscope_targets = []
        datasets_processed = set()
        
        # Read the targets from YAML
        scope = config.get("scope", [])
        for dataset_entry in scope:
            project_id = dataset_entry.get("project")
            dataset_id = dataset_entry.get("dataset")
            tables = dataset_entry.get("tables", [])
            
            if not project_id:
                continue

            # Determine datasets to process: list all if dataset_id is missing
            if dataset_id:
                target_datasets = [dataset_id]
            else:
                datasets = client.list_datasets(project=project_id)
                target_datasets = [d.dataset_id for d in datasets]

            for d_id in target_datasets:
                datasets_processed.add(f"{project_id}.{d_id}")
                
                # Determine tables to process: list all if tables list is empty or missing
                if tables:
                    target_tables = tables
                else:
                    tables_iter = client.list_tables(f"{project_id}.{d_id}")
                    target_tables = [t.table_id for t in tables_iter]

                for table_id in target_tables:
                    inscope_targets.append({
                        "project_id": project_id,
                        "dataset_id": d_id,
                        "table_id": table_id
                    })
        
        print(f"Scope Identification Complete: {len(datasets_processed)} dataset(s) and {len(inscope_targets)} table(s) will be processed.")
        return inscope_targets

    except Exception as e:
        print(f"Error identifying scope: {str(e)}")
        raise e

if __name__ == "__main__":
    # Use the first command-line argument as the path, or default to 'scope.yaml'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        # Default to scope.yaml in the same directory as this script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "scope.yaml")

    targets = identify_scope(config_path)
    for target in targets:
        print(target)
