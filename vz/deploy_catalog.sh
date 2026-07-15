#!/bin/bash
alias gcloud='/apps/opt/application/google-cloud-sdk/bin/gcloud'
set -x
echo "Executing from deploy_catalog.sh"

WORKSPACE_DIR=$1
BRANCH_NAME=$2
GIT_COMMIT_HASH=$3

targetenv="dev"

# --- AUTHENTICATION PRESTEP ---
set +x 
. ~/.bash_profile
set -x 
export http_proxy=http://proxy.ebiz.verizon.com:80
export https_proxy=http://proxy.ebiz.verizon.com:80
setDEVenv
# ------------------------------

echo "Detecting changes for Terraform deployment..."
cd ${WORKSPACE_DIR} 

CHANGED_FOLDERS=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep "cloud_run/" | cut -d/ -f2 | sort | uniq)

# Map the changed folders dynamically to their Terraform variables
TF_VARS=""
for APP_NAME in $CHANGED_FOLDERS; do
    if [ -d "${WORKSPACE_DIR}/cloud_run/${APP_NAME}" ]; then
        # Automatically generates: -var=trust_score_tag=123abc4
        # Automatically generates: -var=profiler_cloud_run_tag=123abc4
        TF_VARS="$TF_VARS -var=${APP_NAME}_tag=${GIT_COMMIT_HASH}"
    fi
done

# Navigate to the Terraform code
cd ${WORKSPACE_DIR}/terraform_code/envs/${targetenv}
echo "Current directory: $(pwd)"

gcloud config list

echo "Cleaning up old Terraform files..."
rm -rf .terraform

echo "Initializing Terraform..."
terraform --version
terraform init

echo "Validating and Planning..."
terraform validate

echo "Running Terraform Plan with dynamic variables: $TF_VARS"
# 'eval' ensures the string of variables is processed correctly by Terraform
eval terraform plan $TF_VARS -out=${targetenv}.tfplan

echo "Applying Terraform..."
terraform apply -auto-approve "${targetenv}.tfplan"

if [[ $? -eq 0 ]]; then 
    echo "Resource creation completed successfully" 
    exit 0
else
    echo "Resource creation failed. Check Terraform logs above."
    exit 1
fi
