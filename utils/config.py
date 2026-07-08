# config.py

from pathlib import Path
import os

# -------- Basic Path Configuration --------
BASE_DIR = Path(__file__).resolve().parents[1]

# Input PDF root directory (can have multiple nested directories)
INPUT_PDF_ROOT = BASE_DIR / "input"

# Output directories unified under output folder
OUTPUT_DIR = BASE_DIR / "output"
PNG_OUTPUT_DIR = OUTPUT_DIR / "png"
OCR_OUTPUT_DIR = OUTPUT_DIR / "ocr_json"
LS_JSON_OUTPUT_DIR = OUTPUT_DIR / "ls_json"
ANNOTATION_OUTPUT_DIR = OUTPUT_DIR / "ls_annotations"
PRESIGNED_URL_OUTPUT_DIR = OUTPUT_DIR / "presigned_url"

OUTPUT_REPORT = OUTPUT_DIR / "evaluation_report.md"

OVERLAP_THRESHOLD = 0.5
FILE_PATTERN = "*.json"

# Ensure directories exist
for d in [PNG_OUTPUT_DIR, OCR_OUTPUT_DIR, LS_JSON_OUTPUT_DIR, ANNOTATION_OUTPUT_DIR, PRESIGNED_URL_OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# -------- MinIO Configuration --------
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "minio"
MINIO_SECRET_KEY = "miniosecret"
MINIO_SECURE = False  # http

MINIO_BUCKET = "security-6"
ANNOTATION_PREFIX = "ls_annotations/"
PNG_DATASET_PREFIX = "png"
PDF_DATASET_PREFIX = "pdf/"
PREDICTION_DATASET_PREFIX = "prediction/"

# MinIO public access URL (for browser / Label Studio to access PNG)
# Generally: https://<endpoint>/<bucket>/<object_name>

MINIO_OK = "localhost:9001"
MINIO_PUBLIC_BASE = f"http://{MINIO_OK}/{MINIO_BUCKET}"

# -------- dots.ocr Configuration --------
EFFORT = "low"  # low, medium, high
OCR_URL = f"https://sp-doc-insight.qa.in.spdigital.sg/ocr/image?effort={EFFORT}"

# -------- Label Studio Configuration --------
LS_BASE = "https://label-studio.qa.in.spdigital.sg"

LS_REFRESH_TOKEN = "4f9469976dedbb4c40746ff2e71cc150dfcd6522"

PROJECT_NAME = "testing-josh"

LS_PROJECT_ID = 12
LS_PAGESIZE = 200