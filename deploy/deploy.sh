#!/bin/bash

# Deployment script for GCP Cloud Run
# Region is set to asia-east1 (Taiwan) to bypass regional restrictions

echo "🚀 Deploying Liquidation API to Google Cloud Run..."

gcloud run deploy liquidation-api \
  --source . \
  --region asia-east1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --set-env-vars "SUPABASE_PROJECT_URL=https://olvftuxfkcllrrhcvqqk.supabase.co,SUPABASE_API_KEY=sb_publishable_lm_p7PQnUq96xdVYS_VR9Q_Dng3N-Gb,ADMIN_SECRET=WYWkVI3fbYCPGu5J"

echo "✅ Deployment command executed."

