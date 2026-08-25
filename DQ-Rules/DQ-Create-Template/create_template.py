import csv
import json
import os
import subprocess
import sys
import yaml


def generate_yaml_from_csv(csv_filepath: str, output_yaml_filepath: str) -> None:
    """Parses rules from a CSV file and converts them into Dataplex Data Quality YAML format."""
    rules_list = []

    if not os.path.exists(csv_filepath):
        raise FileNotFoundError(f"CSV file not found at path: {csv_filepath}")

    with open(csv_filepath, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rule_type = row["rule_type"].strip().upper()
            rule_id = row.get("rule_id", "").strip()
            dimension = row.get("dimension", "VALIDITY").strip().upper()
            description = row.get("description", "").strip()
            expression = row.get("expression", "").strip()

            rule_entry = {
                "dimension": dimension,
            }
            if description:
                rule_entry["description"] = description

            # Map CSV rule types to standard Dataplex Data Quality expectations
            if rule_type == "NOT_NULL":
                rule_entry["nonNullExpectation"] = {}
            elif rule_type in ["RANGE", "CUSTOM_SQL", "ROW_CONDITION"]:
                rule_entry["rowConditionExpectation"] = {
                    "sqlExpression": expression
                }
            elif rule_type == "REGEX":
                rule_entry["regexExpectation"] = {"regex": expression}
            elif rule_type == "SET":
                # Expects a comma-separated list in the expression field
                values = [v.strip() for v in expression.split(",")]
                rule_entry["setExpectation"] = {"values": values}
            else:
                print(
                    f"Warning: Unknown rule_type '{rule_type}' for rule '{rule_id}'. Skipping..."
                )
                continue

            rules_list.append(rule_entry)

    if not rules_list:
        raise ValueError("No valid rules were parsed from the CSV file.")

    # Dataplex expects top-level 'rules' key
    data_quality_spec = {"rules": rules_list}

    with open(output_yaml_filepath, "w", encoding="utf-8") as yml_file:
        yaml.dump(data_quality_spec, yml_file, default_flow_style=False)

    print(
        f"Successfully generated Dataplex YAML spec at: {output_yaml_filepath}"
    )


def create_dataplex_rule_template(
    project_id: str,
    location: str,
    template_id: str,
    display_name: str,
    description: str,
    csv_filepath: str,
) -> None:
    """Converts CSV rules to YAML and executes gcloud CLI to create Dataplex Data Quality Template."""
    temp_yaml_path = "/tmp/generated_rule_template.yaml"

    print(f"--- Starting Rule Template Creation: {template_id} ---")
    print(f"Project ID   : {project_id}")
    print(f"Location     : {location}")
    print(f"Display Name : {display_name}")

    # Step 1: Convert CSV to YAML
    generate_yaml_from_csv(csv_filepath, temp_yaml_path)

    # Step 2: Construct gcloud Command
    # gcloud dataplex data-quality templates create <TEMPLATE_ID>
    cmd = [
        "gcloud",
        "dataplex",
        "data-quality",
        "templates",
        "create",
        template_id,
        f"--project={project_id}",
        f"--location={location}",
        f"--display-name={display_name}",
        f"--description={description}",
        f"--definition-file={temp_yaml_path}",
        "--format=json",  # Captures structured output from gcloud
    ]

    print("\nExecuting Command:")
    print(" ".join(cmd))

    # Step 3: Execute via Subprocess
    try:
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True
        )
        print("\n Template Created Successfully!")
        output_data = json.loads(result.stdout) if result.stdout else {}
        print(
            f"Resource Name: {output_data.get('name', 'Created successfully')}"
        )

    except subprocess.CalledProcessError as e:
        print("\n Failed to create Dataplex Data Quality Rule Template.")
        print(f"Exit Code: {e.returncode}")
        print(f"Error Output:\n{e.stderr}")
        sys.exit(1)
    finally:
        # Cleanup temporary YAML file
        if os.path.exists(temp_yaml_path):
            os.remove(temp_yaml_path)


if __name__ == "__main__":
    # Load configuration from Environment Variables (ideal for Cloud Run) or fallback defaults
    PROJECT_ID = os.environ.get("GCP_PROJECT", "your-gcp-project-id")
    LOCATION = os.environ.get("Gcp_LOCATION", "us-central1")
    TEMPLATE_ID = os.environ.get("TEMPLATE_ID", "csv-generated-dq-template")
    DISPLAY_NAME = os.environ.get(
        "DISPLAY_NAME", "CSV Generated Data Quality Template"
    )
    DESCRIPTION = os.environ.get(
        "DESCRIPTION",
        "Automated Data Quality Rule Template generated from CSV on Cloud Run",
    )
    CSV_FILE_PATH = os.environ.get("CSV_FILE_PATH", "rules.csv")

    create_dataplex_rule_template(
        project_id=PROJECT_ID,
        location=LOCATION,
        template_id=TEMPLATE_ID,
        display_name=DISPLAY_NAME,
        description=DESCRIPTION,
        csv_filepath=CSV_FILE_PATH,
    )