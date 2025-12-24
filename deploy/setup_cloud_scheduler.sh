#!/bin/bash

# Setup Cloud Scheduler to trigger hourly updates
# This ensures the liquidation map updates every hour and saves predictions to Supabase

set -e

PROJECT_ID="crypto-dash-482023"
REGION="asia-east1"
SERVICE_URL="https://liquidation-api-1001101479084.asia-east1.run.app"
JOB_NAME="liquidation-hourly-update"
ADMIN_SECRET="${ADMIN_SECRET:-dev-secret-change-me}"

echo "🚀 Setting up Cloud Scheduler for hourly updates..."
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_URL"
echo "Job Name: $JOB_NAME"
echo ""

# Enable Cloud Scheduler API if needed
echo "🔧 Enabling Cloud Scheduler API..."
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID 2>&1 | grep -v "already enabled" || true

echo ""
echo "📝 Creating/updating scheduler job..."

# Try to create first, if it exists, update it
if gcloud scheduler jobs create http $JOB_NAME \
    --location=$REGION \
    --project=$PROJECT_ID \
    --schedule="0 * * * *" \
    --uri="${SERVICE_URL}/api/admin/update?secret=${ADMIN_SECRET}" \
    --http-method=POST \
    --time-zone="America/New_York" \
    --attempt-deadline=300s \
    --description="Triggers hourly liquidation map update and prediction tracking" \
    2>&1 | grep -q "already exists"; then
    
    echo "⚠️  Job already exists. Updating..."
    gcloud scheduler jobs update http $JOB_NAME \
        --location=$REGION \
        --project=$PROJECT_ID \
        --schedule="0 * * * *" \
        --uri="${SERVICE_URL}/api/admin/update?secret=${ADMIN_SECRET}" \
        --http-method=POST \
        --time-zone="America/New_York" \
        --attempt-deadline=300s
    
    echo "✅ Job updated successfully!"
else
    echo "✅ Job created successfully!"
fi

echo ""
echo "📅 Schedule: Every hour at :00 (0 * * * *)"
echo "🔐 Using ADMIN_SECRET: ${ADMIN_SECRET:0:5}***"
echo ""
echo "🧪 Test the job manually:"
echo "gcloud scheduler jobs run $JOB_NAME --location=$REGION --project=$PROJECT_ID"
echo ""
echo "📊 View job details:"
echo "gcloud scheduler jobs describe $JOB_NAME --location=$REGION --project=$PROJECT_ID"
echo ""
echo "📝 View job logs:"
echo "gcloud logging read 'resource.type=cloud_scheduler_job AND resource.labels.job_id=$JOB_NAME' --limit=10 --format=json"

