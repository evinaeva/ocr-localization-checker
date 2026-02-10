import tempfile
import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from zip_processor import parse_zip_streaming
from app.ocr import process_image

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
async def upload_zip(request: Request, zip_file: UploadFile = File(...)):

    tmp_path = None

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

        # 2. Стриминговый парсинг ZIP
        matches = parse_zip_streaming(tmp_path)

        results = {}

        # Ограничиваемся первыми 10 файлами для теста / снижения нагрузки
        for img_path, img_file_path, ref_text in list(matches)[:10]:
            with open(img_file_path, "rb") as f:
                img_bytes = f.read()

            ocr_text = process_image(img_bytes)

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

    finally:
        # 3. Гарантированно чистим временный ZIP
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
