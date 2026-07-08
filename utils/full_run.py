# utils/run_dotsocr.py

import json
import uuid
import re
import requests
from .config import *
from tqdm import tqdm
import html as html_lib

from pathlib import Path
import base64

def _clean_block_content(raw: str) -> str:
    """Strip HTML tags and markdown heading markers from block content."""
    # Unescape HTML entities first
    text = html_lib.unescape(raw)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove markdown heading markers (##, ###, etc.)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

def run_paddleOCR(local_png_path):
    with open(local_png_path, "rb") as f:
        files = {"file": ("image.png", f, "image/png")}
        resp = requests.post(
            OCR_URL,
            files=files,
            timeout=120
        )
    resp.raise_for_status()
    return resp.json()

def convert_ocr_to_ls_prediction(ocr_output: dict, img_w: int, img_h: int):
    """
    Convert OCR output into the correct Label Studio prediction format.
    Rectangle, Labels, TextArea must share the SAME region_id.
    """
    results = []

    grounding = ocr_output.get("GROUNDING", {})
    elements = grounding.get("parsing_res_list", [])

    for el in elements:
        x0, y0, x1, y1 = el["block_bbox"]
        label = el.get("block_label", "text")
        text = _clean_block_content(el.get("block_content", ""))

        px = x0 / img_w * 100
        py = y0 / img_h * 100
        pw = (x1 - x0) / img_w * 100
        ph = (y1 - y0) / img_h * 100

        # ⭐ SAME region id for all 3 items
        region_id = str(uuid.uuid4())[:10]

        base_value = {
            "x": px,
            "y": py,
            "width": pw,
            "height": ph,
            "rotation": 0,
        }

        # 1) Rectangle
        results.append({
            "id": region_id,                 # SAME ID
            "type": "rectangle",
            "origin": "prediction",
            "from_name": "bbox",
            "to_name": "image",
            "value": base_value,
            "score": 0.99,
            "image_rotation": 0,
            "original_width": img_w,
            "original_height": img_h,
        })

        # 2) Labels
        v2 = base_value.copy()
        v2["labels"] = [label]

        results.append({
            "id": region_id,                 # SAME ID
            "type": "labels",
            "origin": "prediction",
            "from_name": "label",
            "to_name": "image",
            "value": v2,
            "score": 0.99,
            "image_rotation": 0,
            "original_width": img_w,
            "original_height": img_h,
        })

        # 3) Textarea
        v3 = base_value.copy()
        v3["text"] = [text]

        results.append({
            "id": region_id,                 # SAME ID
            "type": "textarea",
            "origin": "prediction",
            "from_name": "transcription",
            "to_name": "image",
            "value": v3,
            "score": 0.99,
            "image_rotation": 0,
            "original_width": img_w,
            "original_height": img_h,
        })

    prediction = {
        "model_version": "ocr-prelabel-v1",
        "score": 1.0,
        "result": results,
    }
    return prediction

def run_ocr_to_ls(uploaded):
    for item in uploaded:
        local_png = item["local_path"]
        img_w = item["width"]
        img_h = item["height"]
        png_name = Path(local_png).name
    
        print(f"processing {local_png}")
        ocr_output = run_paddleOCR(local_png)
    
        ocr_out_path = OCR_OUTPUT_DIR / (Path(local_png).stem + ".json")
        with open(ocr_out_path, "w", encoding="utf-8") as f:
            json.dump(ocr_output, f, ensure_ascii=False, indent=2)
    
        prediction = convert_ocr_to_ls_prediction(ocr_output, img_w, img_h)
    
        print(f"processing prediction..{item}")
        print("   ")
        ls_jsonl_path = LS_JSON_OUTPUT_DIR / (Path(local_png).stem + ".jsonl")
    
        with ls_jsonl_path.open("a", encoding="utf-8") as f:
            rec = {
                "png_filename": png_name,
                "prediction": prediction,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def run_dotsocr_local_file(local_path: str):
    with open(local_path, "rb") as f:
        files = {"file": f}
        resp = requests.post(OCR_URL, files=files, timeout=120)
        resp.raise_for_status()
        return resp.json()
    
# Step 2 

LS_JSON_DIR = Path(LS_JSON_OUTPUT_DIR)


def _ls_headers():
    return {"Authorization": f"Token {LS_REFRESH_TOKEN}"}


def get_project_id_by_title(project_title: str) -> int:
    resp = requests.get(f"{LS_BASE}/api/projects", headers=_ls_headers(), params={"page_size": 200})
    resp.raise_for_status()
    projects = resp.json().get("results", [])

    wanted = (project_title or "").strip().lower()

    print("[DEBUG] Available projects:")
    for p in projects:
        print(f"  - id={p['id']} title={repr(p['title'])}")

    for p in projects:
        if (p["title"] or "").strip().lower() == wanted:
            return p["id"]

    for p in projects:
        if wanted and wanted in (p["title"] or "").strip().lower():
            print(f"[DEBUG] Fuzzy matched project: id={p['id']} title={repr(p['title'])}")
            return p["id"]

    raise RuntimeError(f"Project not found (wanted={repr(project_title)})")


def push_prediction(project_id: int, png_filename: str, prediction: dict):
    fileuri = f"{MINIO_PUBLIC_BASE}/{PNG_DATASET_PREFIX}/{png_filename}"

    payload = [{
        "data": {"ocr": fileuri},
        "predictions": [{
            "result": prediction["result"],
            "model_version": "dotsocr",
        }]
    }]

    resp = requests.post(
        f"{LS_BASE}/api/projects/{project_id}/import",
        headers=_ls_headers(),
        json=payload,
    )
    resp.raise_for_status()

def push_all_predictions_to_ls():
    """
    读取 output/ls_json/*.jsonl
    格式示例：
       {"png_filename": "...", "prediction": {...}}
    """
    project_id = get_project_id_by_title(PROJECT_NAME)

    jsonl_files = sorted(LS_JSON_DIR.glob("*.jsonl"))
    seen = set()  # png_filename 去重：避免同一张图重复 import

    pushed = 0
    skipped = 0

    for jsonl_path in jsonl_files:
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                rec = json.loads(line)
                png_filename = rec["png_filename"]
                prediction = rec["prediction"]

                if png_filename in seen:
                    skipped += 1
                    continue
                seen.add(png_filename)

                push_prediction(project_id, png_filename, prediction)
                pushed += 1

    print(f"[DONE] pushed={pushed}, skipped={skipped}, project_id={project_id}")


# ---------------------------------------------------------------------------
# FULL RUN orchestrator (one notebook cell)
# ---------------------------------------------------------------------------

# Imported here (not at module top) so the SDK import inside export.py — if it
# ever fails on Python 3.9 — cannot break importing this module.
from .export import upload_png_list_to_minio


def full_run(png_list):
    """
    FULL RUN stage: take the PNGs produced by INPUT, get them into MinIO + Label
    Studio with OCR pre-labels. Runs as a single notebook cell.

    :param png_list: list of dicts from batch_pdf_to_png()
    """
    # Step 1: Upload PNGs to MinIO so Label Studio can display them
    upload_png_list_to_minio(PNG_DATASET_PREFIX, png_list)

    # Step 2: Run OCR and build Label Studio predictions
    run_ocr_to_ls(png_list)

    # Step 3: Push predictions to Label Studio
    push_all_predictions_to_ls()