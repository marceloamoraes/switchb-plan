"""Cloud Run service: Phase 2 targeted AI extraction.

Receives a Pub/Sub push message from Phase 1 (only for documents that matched the
keyword filter), reads the extracted text from GCS, runs a structured-output Gemini
call, and writes the resulting row to BigQuery.
"""
import datetime
import json
import logging
import os

from flask import Flask, request
from google import genai
from google.cloud import bigquery, storage

from schema import RESPONSE_SCHEMA, build_prompt

PROJECT_ID = os.environ["PROJECT_ID"]
REGION = os.environ.get("REGION", "us-central1")
BQ_TABLE = os.environ["BQ_TABLE"]  # e.g. project.dataset.table
# Original spec named "Gemini 1.5 Flash"; that generation is retired on Vertex AI,
# so this defaults to the current cost-tier equivalent. Override via env var.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
storage_client = storage.Client()
bq_client = bigquery.Client()
genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)


@app.post("/")
def handle_pubsub_push():
    envelope = request.get_json(force=True, silent=True) or {}
    message = envelope.get("message", {})
    data = message.get("data")

    if not data:
        return ("", 204)

    import base64
    payload = json.loads(base64.b64decode(data).decode("utf-8"))

    try:
        process_message(payload)
    except Exception:
        logging.exception("Failed to extract for payload: %s", payload)
        return ("processing error", 500)  # let Pub/Sub retry

    return ("", 204)


def process_message(payload: dict):
    bucket_name = payload["bucket"]
    source_object = payload["source_object"]
    text_object = payload["text_object"]

    text = storage_client.bucket(bucket_name).blob(text_object).download_as_text()

    response = genai_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=build_prompt(text),
        config={
            "response_mime_type": "application/json",
            "response_schema": RESPONSE_SCHEMA,
        },
    )
    extracted = json.loads(response.text)

    row = {
        **extracted,
        "source_uri": f"gs://{bucket_name}/{source_object}",
        "processed_at": datetime.datetime.utcnow().isoformat(),
    }
    errors = bq_client.insert_rows_json(BQ_TABLE, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert failed: {errors}")

    logging.info("Extracted and stored: %s", source_object)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
