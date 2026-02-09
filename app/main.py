from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from zip_processor import parse_zip  # 🔥 НОВЫЙ ИМПОРТ
from app.ocr import process_image     # ⭐ СТАРЫЙ OCR (НЕ ТРОГАЕМ)
import os

app = FastAPI()

# 🔹 Определяем абсолютный путь к папке templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/", response_class=HTMLResponse)
async def upload_zip(request: Request, zip_file: UploadFile = File(...)):
    zip_bytes = await zip_file.read()
    
    # 🔥 НОВЫЙ КОД: ZIP → matches
    matches = parse_zip(zip_bytes)
    
    # Обработка (первые 10 файлов для демо)
    results = {}
    for img_path, (img_bytes, ref_text) in list(matches.items())[:10]:
        ocr_text = process_image(img_bytes)  # ⭐ СТАРЫЙ VISION OCR
        
        # 100% точное совпадение
        is_match = ocr_text.strip() == ref_text.strip()
        
        results[img_path] = {
            "image": img_path,
            "reference": ref_text,
            "ocr": ocr_text,
            "match": is_match,
            "status": "✅ PASS" if is_match else "❓ MANUAL"
        }
    
    total = len(matches)
    manual_count = sum(1 for r in results.values() if not r["match"])
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "results": results,
            "total_files": total,
            "manual_count": manual_count
        }
    )