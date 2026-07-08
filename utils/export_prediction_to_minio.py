# export_prediction_to_minio.py
#
# EXPORT stage: upload all output files to MinIO.

from pathlib import Path

from minio import Minio

from .config import *


# Single MinIO client for this step (self-contained).
client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)


def _ls_headers():
    return {"Authorization": f"Token {LS_REFRESH_TOKEN}"}


def ensure_bucket():
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)


def upload_all_outputs_to_minio():
    """Upload all output subdirectories to MinIO under the output/ prefix."""
    ensure_bucket()

    output_dirs = {
        "ocr_json": OCR_OUTPUT_DIR,
        "ls_json": LS_JSON_OUTPUT_DIR,
        "presigned_url": PRESIGNED_URL_OUTPUT_DIR,
        "ls_annotations": ANNOTATION_OUTPUT_DIR,
        "png": PNG_OUTPUT_DIR,
    }

    pushed = 0
    for prefix, directory in output_dirs.items():
        for p in sorted(directory.glob("*")):
            if p.is_file():
                object_name = f"output/{prefix}/{p.name}"
                client.fput_object(
                    MINIO_BUCKET,
                    object_name,
                    str(p),
                    content_type="application/json",
                )
                pushed += 1
                print(f"[OK] {p.name} -> s3://{MINIO_BUCKET}/{object_name}")

    print(f"[DONE] pushed={pushed} output files to bucket={MINIO_BUCKET}")
    return pushed


def export_prediction_to_minio():
    # Upload all output folders to MinIO
    upload_all_outputs_to_minio()