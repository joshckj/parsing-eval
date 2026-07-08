# run_png_to_ocr.py
#
# FULL RUN — Step 2: run the OCR service on each page PNG, save the raw output,
# and convert it into Label Studio prediction format for the push step.

import json
import uuid
import re
import html as html_lib
from pathlib import Path

import requests

from .config import *


# Confidence used for a block that has no matching layout-detection box.
DEFAULT_SCORE = 1.0


def _clean_block_content(raw: str) -> str:
    """Turn a raw OCR block into plain text fit for a Label Studio transcription.

    Unescapes HTML entities, strips HTML tags and markdown heading markers, and
    collapses whitespace. Used so the `textarea` value shows readable text rather
    than the markup the OCR service returns.
    """
    text = html_lib.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def run_paddleOCR(local_png_path):
    """POST a single PNG to the OCR service (`OCR_URL`) and return the parsed JSON.

    Raises for any non-2xx response so callers fail fast on a bad request. This is
    the only network call in this module; everything else transforms its output.
    """
    with open(local_png_path, "rb") as f:
        files = {"file": ("image.png", f, "image/png")}
        resp = requests.post(
            OCR_URL,
            files=files,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def convert_ocr_to_ls_prediction(ocr_output: dict, img_w: int, img_h: int):
    """Convert one page's OCR output into a Label Studio prediction dict.

    For every detected block it emits three regions (rectangle, labels, textarea)
    that share one `region_id`, with bbox coordinates rescaled to percentages of
    the image size. Each region's `score` is the block's real layout-detection
    confidence (falling back to DEFAULT_SCORE). Returns the
    `{model_version, score, result}` prediction the push step imports.
    """
    results = []

    grounding = ocr_output.get("GROUNDING", {})
    elements = grounding.get("parsing_res_list", [])

    # Real per-block confidence lives in layout_det_res.boxes (parsing_res_list
    # has none); match a parsing block to its detection box by identical bbox.
    layout_boxes = grounding.get("layout_det_res", {}).get("boxes", [])
    score_by_bbox = {tuple(b["coordinate"]): b["score"] for b in layout_boxes}

    for el in elements:
        x0, y0, x1, y1 = el["block_bbox"]
        label = el.get("block_label", "text")
        text = _clean_block_content(el.get("block_content", ""))
        score = score_by_bbox.get(tuple(el["block_bbox"]), DEFAULT_SCORE)

        px = x0 / img_w * 100
        py = y0 / img_h * 100
        pw = (x1 - x0) / img_w * 100
        ph = (y1 - y0) / img_h * 100

        # SAME region id for all 3 items so LS treats them as one region
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
            "id": region_id,
            "type": "rectangle",
            "origin": "prediction",
            "from_name": "bbox",
            "to_name": "image",
            "value": base_value,
            "score": score,
            "image_rotation": 0,
            "original_width": img_w,
            "original_height": img_h,
        })

        # 2) Labels
        v2 = base_value.copy()
        v2["labels"] = [label]

        results.append({
            "id": region_id,
            "type": "labels",
            "origin": "prediction",
            "from_name": "label",
            "to_name": "image",
            "value": v2,
            "score": score,
            "image_rotation": 0,
            "original_width": img_w,
            "original_height": img_h,
        })

        # 3) Textarea
        v3 = base_value.copy()
        v3["text"] = [text]

        results.append({
            "id": region_id,
            "type": "textarea",
            "origin": "prediction",
            "from_name": "transcription",
            "to_name": "image",
            "value": v3,
            "score": score,
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


def run_png_to_ocr(png_list):
    """Run OCR on every page PNG and stage the results for the push step.

    For each PNG it calls the OCR service, saves the raw JSON to `ocr_json/`,
    converts it to a Label Studio prediction, and appends a
    `{png_filename, prediction}` record to `ls_json/<stem>.jsonl`. Takes the
    `png_list` produced by `batch_pdf_to_png()` in INPUT.
    """
    for item in png_list:
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

        with ls_jsonl_path.open("w", encoding="utf-8") as f:
            rec = {
                "png_filename": png_name,
                "prediction": prediction,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")