#!/bin/bash
TOKEN=$(gcloud auth print-access-token)
# Wipe conflicting config
rm -f ~/.docker/config.json
rm -f ~/.config/containers/auth.json
echo "{}" > ~/.docker/config.json

podman login -u oauth2accesstoken -p "$TOKEN" https://us-central1-docker.pkg.dev

cd /mnt/c/Users/aslahfaseel.k/Desktop/vz-code/vz-kc-release/vz_knowledge_catalog_automation-feature_prod_branch/vz_knowledge_catalog_automation-feature_prod_branch/cloud_run/custom_dq_scan

podman build -t us-central1-docker.pkg.dev/dmgcp-del-181/cloud-run-source-deploy/custom_dq_scan:latest .
podman push us-central1-docker.pkg.dev/dmgcp-del-181/cloud-run-source-deploy/custom_dq_scan:latest
