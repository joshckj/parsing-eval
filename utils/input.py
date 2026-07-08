import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
from .config import *
from typing import Any, Dict, List

def list_all_pdfs(root_folder):
    pdf_list = []
    root = Path(root_folder)
    for file in root.rglob("*.pdf"):
        if any(part == ".ipynb_checkpoints" for part in file.parts):
            continue
        pdf_list.append(str(file))
    return pdf_list

def make_png_name(pdf_path: Path, page_num: int) -> str:

    pdf_path = pdf_path.resolve()
    parent_name = pdf_path.parent.name  # e.g. dcc-chatbot
    stem = pdf_path.stem.replace(" ", "_")  # Security_Deposit_amount_for_different_premises
    return f"{parent_name}-{stem}_page_{page_num}.png"

def fitz_page_to_pil(page: fitz.Page, dpi: int = 300) -> Image.Image:
    """
    Render a single PyMuPDF page into a PIL Image at target DPI.
    """
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pm = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)

# def pdf_to_png(pdf_path_str: str, dpi: int = 300) -> List[Dict[str, Any]]:
def batch_pdf_to_png(pdf_list: List, dpi: int = 300) -> List[Dict[str, Any]]:

    """
    Convert a PDF into PNG images using PyMuPDF.

    Args:
        pdf_path_str: path to PDF file
        dpi: target DPI for rendering

    Returns:
        [
          {"png_path": "...", "width": 1234, "height": 2345},
          ...
        ]
    """

    png_list = []

    for pdf_path in pdf_list:
   
        pdf_path = Path(pdf_path).resolve()
    
        out_dir = PNG_OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
    
        with fitz.open(pdf_path) as doc:
            for idx, page in enumerate(doc, start=1):
                results = {}
                img = fitz_page_to_pil(page, dpi=dpi)
    
                output_file = out_dir / f"{pdf_path.stem}_page_{idx}.png"
                img.save(output_file, format="PNG")
    
                # results.append({
                #     "local_path": str(output_file),
                #     "width": img.width,
                #     "height": img.height,
                # })
                results["local_path"] = output_file
                results["width"] = img.width
                results["height"] = img.height
                
                png_list.append(results)

    return png_list