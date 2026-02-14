import tempfile
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from zip_processor import parse_zip_streaming
from app.ocr import process_image
from worker.normalization import normalize_strict, normalize_soft
from shared.docx_section_extractor import extract_section_candidates
from shared.reference_matcher import select_best_section

# --- Определяем базовую директорию и шаблоны ---
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI()

from app.jobs_api import router as jobs_router
app.include_router(jobs_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/", response_class=HTMLResponse)
async def upload_zip(
    request: Request, 
    zip_file: UploadFile = File(...),
    section_number: Optional[str] = Form(None),
    section_name: Optional[str] = Form(None),
):
    tmp_path = None
    work_dir = None

    try:
        # 1. Пишем ZIP во временный файл, НЕ в память
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

            while True:
                chunk = await zip_file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                tmp.write(chunk)

            tmp.flush()

        # 2. Стриминговый парсинг ZIP (extended mode)
        matches, work_dir = parse_zip_streaming(tmp_path, return_work_dir=True, return_extended=True)

        results = {}
        ui_warnings = []

        # Ограничиваемся первыми 10 файлами для теста / снижения нагрузки
        for img_path, img_file_path, ref_text, ref_bytes, language in list(matches)[:10]:
            with open(img_file_path, "rb") as f:
                img_bytes = f.read()

            # 1. Extract OCR text
            ocr_text = process_image(img_bytes)
            
            # Derive DOCX filename from img_path
            # img_path format: "images/banner_01_(en).png"
            # ref_path format: "texts/banner_01_(en).docx"
            ref_path = img_path.replace("images/", "texts/").rsplit(".", 1)[0]
            docx_filename = os.path.basename(ref_path + ".docx")
            
            # 2. Extract section candidates from reference DOCX
            candidates = []
            if ref_bytes and ref_bytes[:2] == b'PK':  # Check if it's a ZIP/DOCX
                try:
                    candidates = extract_section_candidates(ref_bytes, docx_filename, language)
                except Exception as e:
                    ui_warnings.append(f"Failed to extract sections from {docx_filename}: {str(e)}")
            
            # 3. Select best section
            if candidates:
                selection = select_best_section(
                    ocr_text=ocr_text,
                    candidates=candidates,
                    normalize_strict_fn=normalize_strict,
                    normalize_soft_fn=normalize_soft,
                    section_number=section_number.strip() if section_number else None,
                    section_name=section_name.strip() if section_name else None,
                )
                
                selected_ref_text = selection.chosen_text
                is_match = normalize_strict(ocr_text) == normalize_strict(selected_ref_text)
                
                # Collect warnings
                if selection.warnings:
                    ui_warnings.extend(selection.warnings)
                
                # Status based on manual_required flag
                status = "✅ PASS" if is_match and not selection.manual_required else "❓ MANUAL"
                
                results[img_path] = {
                    "image": img_path,
                    "reference": selected_ref_text,
                    "ocr": ocr_text,
                    "match": is_match,
                    "status": status,
                    "selection": selection.to_dict(),
                }
            else:
                # Fallback to old behavior
                is_match = ocr_text.strip() == ref_text.strip()
                results[img_path] = {
                    "image": img_path,
                    "reference": ref_text,
                    "ocr": ocr_text,
                    "match": is_match,
                    "status": "✅ PASS" if is_match else "❓ MANUAL",
                    "selection": {
                        "manual_required": not is_match,
                    },
                }

        total = len(matches)
        # Count manual_required from selection metadata
        manual_count = sum(
            1 for r in results.values()
            if r.get("selection", {}).get("manual_required", False)
        )

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "results": results,
                "total_files": total,
                "manual_count": manual_count,
                "warnings": ui_warnings,
                "section_number": section_number,
                "section_name": section_name,
            },
        )

    finally:
        # 3. Гарантированно чистим временный ZIP
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
