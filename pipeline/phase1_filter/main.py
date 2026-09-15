"""Cloud Run service: Phase 1 local pre-filter.

Receives a Pub/Sub push message describing one GCS object — published manually via
`scripts/trigger_phase1.py`, not automatically on upload — extracts text locally,
and either archives the object (no keyword match) or hands it to Phase 2 (match) by
writing the text to GCS and publishing a message.
"""
import base64
import json
import logging
import os
import tempfile

from flask import Flask, request
from google.api_core.exceptions import NotFound
from google.cloud import pubsub_v1, storage

from matcher import is_match
from parsers import extract_text

BUCKET_NAME = os.environ["BUCKET_NAME"]
ARCHIVE_PREFIX = os.environ.get("ARCHIVE_PREFIX", "archive/")
EXTRACTED_PREFIX = os.environ.get("EXTRACTED_PREFIX", "extracted/")
PROJECT_ID = os.environ["PROJECT_ID"]
PHASE2_TOPIC = os.environ["PHASE2_TOPIC"]

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
phase2_topic_path = publisher.topic_path(PROJECT_ID, PHASE2_TOPIC)


@app.post("/")
def handle_pubsub_push():
    envelope = request.get_json(force=True, silent=True) or {}
    message = envelope.get("message", {})
    attributes = message.get("attributes", {})

    event_type = attributes.get("eventType")
    bucket_name = attributes.get("bucketId")
    object_name = attributes.get("objectId")

    if event_type != "OBJECT_FINALIZE" or not bucket_name or not object_name:
        # Not a finalize event (or a malformed push) — ack and move on.
        return ("", 204)

    if object_name.startswith(ARCHIVE_PREFIX) or object_name.startswith(EXTRACTED_PREFIX):
        return ("", 204)

    try:
        process_object(bucket_name, object_name)
    except Exception:
        logging.exception("Failed to process gs://%s/%s", bucket_name, object_name)
        return ("processing error", 500)  # let Pub/Sub retry

    return ("", 204)


def process_object(bucket_name: str, object_name: str):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    archive_blob_name = ARCHIVE_PREFIX + object_name
    text_blob_name = EXTRACTED_PREFIX + object_name + ".txt"

    suffix = os.path.splitext(object_name)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        try:
            blob.download_to_filename(tmp.name)
        except NotFound:
            # Redelivered message for an object already moved by a prior attempt.
            if bucket.blob(archive_blob_name).exists() or bucket.blob(text_blob_name).exists():
                logging.info("Already processed, skipping redelivery: %s", object_name)
                return
            raise
        text = extract_text(tmp.name)

    if not is_match(text):
        bucket.copy_blob(blob, bucket, archive_blob_name)
        blob.delete()
        logging.info("No match, archived: %s", object_name)
        return

    bucket.blob(text_blob_name).upload_from_string(text, content_type="text/plain")

    payload = {
        "bucket": bucket_name,
        "source_object": object_name,
        "text_object": text_blob_name,
    }
    publisher.publish(phase2_topic_path, json.dumps(payload).encode("utf-8"))
    logging.info("Match, queued for extraction: %s", object_name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
