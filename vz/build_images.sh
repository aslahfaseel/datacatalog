#!/bin/bash
alias gcloud='/apps/opt/application/google-cloud-sdk/bin/gcloud'
set -x

WORKSPACE_DIR=$1
GIT_COMMIT_HASH=$2 

# --- AUTHENTICATION PRESTEP ---
set +x 
. ~/.bash_profile
set -x 

export http_proxy=http://proxy.ebiz.verizon.com:80
export https_proxy=http://proxy.ebiz.verizon.com:80

setDEVenv
# ------------------------------

# Target Artifact Registry & Cloud Build Variables
AR_REGION="us-east4"
PROJECT_ID="vz-it-np-keiv-dev-dpev-0"
REPO_NAME="vz-it-keiv-dpev-0-docker"
BASE_IMAGE_URI="${AR_REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
BUILD_SA="projects/${PROJECT_ID}/serviceAccounts/sa-dev-keiv-app-dpev-0@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Detecting changes in cloud_run directories..."
cd ${WORKSPACE_DIR}

# Find which folders inside cloud_run/ were modified
CHANGED_FOLDERS=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep "cloud_run/" | cut -d/ -f2 | sort | uniq)

# Fallback for fresh runs or Jenkins shallow clones
if [ $? -ne 0 ] || [ -z "$CHANGED_FOLDERS" ]; then
    echo "Warning: Git diff failed or no changes found. Checking if this is a fresh run..."
    CHANGED_FOLDERS=$(ls -1 ${WORKSPACE_DIR}/cloud_run/ 2>/dev/null)
fi

if [ -z "$CHANGED_FOLDERS" ]; then
    echo "No cloud_run applications found to build."
else
    for APP_NAME in $CHANGED_FOLDERS; do
        APP_DIR="${WORKSPACE_DIR}/cloud_run/${APP_NAME}"
        
        if [ -d "$APP_DIR" ]; then
            echo "Building image for: ${APP_NAME} using ONLY commit hash tag"
            
            gcloud builds submit "${APP_DIR}" \
                --tag="${BASE_IMAGE_URI}/${APP_NAME}:${GIT_COMMIT_HASH}" \
                --project="${PROJECT_ID}" \
                --service-account="${BUILD_SA}" \
                --default-buckets-behavior=REGIONAL_USER_OWNED_BUCKET
                
            if [[ $? -ne 0 ]]; then 
                echo "Failed to build image for ${APP_NAME}"
                exit 1
            fi
        fi
    done
    echo "All applicable images built and pushed successfully!"
fi
