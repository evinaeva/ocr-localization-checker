from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.ocr import process_image

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = process_image(image_bytes)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": result}
    )
