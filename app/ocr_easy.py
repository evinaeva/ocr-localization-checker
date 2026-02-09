# app/ocr_easy.py

import io
from typing import Optional

import easyocr
from PIL import Image


# Инициализируем reader один раз на процесс, чтобы не платить за создание на каждый запрос.
# Для баннеров достаточно языков EN + основные европейские.
# Явно отключаем GPU, так как Cloud Run по умолчанию без GPU.
_reader: Optional[easyocr.Reader] = None


def get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        # При необходимости добавим другие языки (ru, de, fr, ja и т.п.) в следующих шагах.
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def run_easyocr(image_bytes: bytes) -> str:
    """
    Layer: EasyOCR.
    Вход: сырые байты изображения (PNG/JPG).
    Выход: один строковый текст, склеенный из всех найденных фрагментов.
    """
    # Дополнительная защита: убеждаемся, что это валидное изображение.
    try:
        Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        return f"EasyOCR error: invalid image ({exc})"

    reader = get_reader()

    try:
        # detail=0 → список строк; paragraph=True пробует объединять строки логически.
        result = reader.readtext(image_bytes, detail=0, paragraph=True)
    except Exception as exc:
        return f"EasyOCR error: {exc}"

    if not result:
        return "No text detected (EasyOCR)."

    # Склеиваем блоки в одну строку — в консенсус‑логике будет отдельная нормализация.
    return "\n".join(block.strip() for block in result if isinstance(block, str) and block.strip())
