"""Manually kick off Phase 1 processing for objects already sitting in the bucket.

Ingestion (uploading files to GCS) and processing are decoupled on purpose: nothing
runs automatically when a file lands in the bucket. Upload whenever you want, then
run this script when you're ready to start (or re-start) a processing batch.

Publishes one Pub/Sub message per object, in the same attribute shape
pipeline/phase1_filter/main.py expects from a GCS OBJECT_FINALIZE event, so the
Cloud Run service itself needs no changes.

Usage:
  python scripts/trigger_phase1.py --project PROJECT --bucket BUCKET \
      [--topic phase1-trigger] [--prefix some/subfolder/] [--dry-run]
"""
import argparse

from google.cloud import pubsub_v1, storage

SKIP_PREFIXES = ("archive/", "extracted/")


def iter_source_objects(bucket, prefix: str):
    for blob in bucket.list_blobs(prefix=prefix):
        if blob.name.endswith("/"):
            continue
        if any(blob.name.startswith(p) for p in SKIP_PREFIXES):
            continue
        yield blob


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--topic", default="phase1-trigger")
    parser.add_argument("--prefix", default="", help="Only trigger objects under this prefix")
    parser.add_argument("--dry-run", action="store_true", help="List what would be published, don't publish")
    args = parser.parse_args()

    bucket = storage.Client(project=args.project).bucket(args.bucket)
    objects = list(iter_source_objects(bucket, args.prefix))

    print(f"Found {len(objects)} object(s) to trigger under gs://{args.bucket}/{args.prefix}")
    if args.dry_run:
        for blob in objects[:20]:
            print(f"  {blob.name}")
        if len(objects) > 20:
            print(f"  ... and {len(objects) - 20} more")
        return

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(args.project, args.topic)

    futures = [
        publisher.publish(
            topic_path, b"",
            eventType="OBJECT_FINALIZE", bucketId=args.bucket, objectId=blob.name,
        )
        for blob in objects
    ]
    for i, future in enumerate(futures, start=1):
        future.result()
        if i % 500 == 0:
            print(f"Published {i}/{len(objects)}...")

    print(f"Done. Published {len(objects)} message(s) to {topic_path}.")


if __name__ == "__main__":
    main()
