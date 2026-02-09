from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from zip_processor import parse_zip
from app.ocr import process_image  # Google Vision
from app.ocr_easy import run_easyocr  # EasyOCR

import os

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/", response_class=HTMLResponse)
async def upload_zip(request: Request, zip_file: UploadFile = File(...)):
    zip_bytes = await zip_file.read()

    # ZIP → словарь {img_path: (img_bytes, ref_text)}
    matches = parse_zip(zip_bytes)

    # Обработка (первые 10 файлов для демо)
    results = {}
    for img_path, (img_bytes, ref_text) in list(matches.items())[:10]:
        # Layer 3: Google Vision (как было)
        vision_text = process_image(img_bytes)

        # Layer EasyOCR: дополнительный результат (не влияет на статус сейчас)
        easy_text = run_easyocr(img_bytes)

        # 100% точное совпадение — ПОКА только по Vision,
        # консенсус будет отдельным шагом.
        is_match = vision_text.strip() == ref_text.strip()

        results[img_path] = {
            "image": img_path,
            "reference": ref_text,
            "ocr_vision": vision_text,
            "ocr_easy": easy_text,
            "match": is_match,
            "status": "✅ PASS" if is_match else "❓ MANUAL",
        }

    total = len(matches)
    manual_count = sum(1 for r in results.values() if not r["match"])

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "results": results,
            "total_files": total,
            "manual_count": manual_count,
        },
    )
