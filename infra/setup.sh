#!/usr/bin/env bash
# Reference setup script. Edit the variables below, then run section by section
# (not meant to be executed unattended).
set -euo pipefail

PROJECT_ID="your-gcp-project"
REGION="us-central1"
BUCKET_NAME="your-switchgear-docs-bucket"
DATASET="switchgear"
TABLE="extracted_specs"
PHASE1_TOPIC="phase1-trigger"
PHASE2_TOPIC="phase2-trigger"

gcloud config set project "$PROJECT_ID"

# --- 1. Storage bucket + lifecycle rule scoped to archive/ ---
gcloud storage buckets create "gs://$BUCKET_NAME" --location="$REGION"
gcloud storage buckets update "gs://$BUCKET_NAME" --lifecycle-file=lifecycle.json

# --- 2. Pub/Sub topics + GCS notification for Phase 1 ---
gcloud pubsub topics create "$PHASE1_TOPIC"
gcloud pubsub topics create "$PHASE2_TOPIC"
gsutil notification create -t "$PHASE1_TOPIC" -f json -e OBJECT_FINALIZE "gs://$BUCKET_NAME"

# --- 3. BigQuery dataset + table ---
bq mk --dataset --location="$REGION" "$PROJECT_ID:$DATASET"
bq mk --table "$PROJECT_ID:$DATASET.$TABLE" bigquery_schema.json

# --- 4. Build + deploy Phase 1 (Cloud Run) ---
gcloud builds submit ../pipeline/phase1_filter \
  --tag "gcr.io/$PROJECT_ID/phase1-filter"
gcloud run deploy phase1-filter \
  --image "gcr.io/$PROJECT_ID/phase1-filter" \
  --region "$REGION" --no-allow-unauthenticated \
  --set-env-vars "PROJECT_ID=$PROJECT_ID,BUCKET_NAME=$BUCKET_NAME,PHASE2_TOPIC=$PHASE2_TOPIC"

PHASE1_URL=$(gcloud run services describe phase1-filter --region "$REGION" --format='value(status.url)')
gcloud pubsub subscriptions create phase1-sub \
  --topic "$PHASE1_TOPIC" --push-endpoint="$PHASE1_URL" \
  --push-auth-service-account="run-invoker@$PROJECT_ID.iam.gserviceaccount.com"

# --- 5. Build + deploy Phase 2 (Cloud Run) ---
gcloud builds submit ../pipeline/phase2_extract \
  --tag "gcr.io/$PROJECT_ID/phase2-extract"
gcloud run deploy phase2-extract \
  --image "gcr.io/$PROJECT_ID/phase2-extract" \
  --region "$REGION" --no-allow-unauthenticated \
  --set-env-vars "PROJECT_ID=$PROJECT_ID,REGION=$REGION,BQ_TABLE=$PROJECT_ID.$DATASET.$TABLE"

PHASE2_URL=$(gcloud run services describe phase2-extract --region "$REGION" --format='value(status.url)')
gcloud pubsub subscriptions create phase2-sub \
  --topic "$PHASE2_TOPIC" --push-endpoint="$PHASE2_URL" \
  --push-auth-service-account="run-invoker@$PROJECT_ID.iam.gserviceaccount.com"
