#!/bin/bash

# Deployment script for GCP Cloud Run
# Region is set to asia-east1 (Taiwan) to bypass regional restrictions

echo "🚀 Deploying Liquidation API to Google Cloud Run..."

gcloud run deploy liquidation-api \
  --source . \
  --region asia-east1 \
  --allow-unauthenticated \
  --port 8080

echo "✅ Deployment command executed."

