import zipfile
import tempfile
import os
import shutil
from pathlib import Path
from typing import List, Tuple, Union

from docx import Document
import io


def parse_zip_streaming(
    zip_path: str,
    *,
    return_work_dir: bool = False,
) -> Union[List[Tuple[str, str, str]], Tuple[List[Tuple[str, str, str]], str]]:
    """
    Парсит ZIP и извлекает изображения во временную директорию.

    ВАЖНО:
    - Если return_work_dir=False (по умолчанию) — возвращает только matches (backward-compatible).
      В этом режиме ответственность за cleanup остаётся вне функции (как и было раньше).
    - Если return_work_dir=True — возвращает (matches, work_dir), и caller обязан удалить work_dir.
      Это нужно, чтобы корректно убрать утечки temp-файлов, не ломая логику чтения img_file_path.
    """
    results: List[Tuple[str, str, str]] = []
    work_dir = tempfile.mkdtemp(prefix="ocr_zip_")

    images = {}
    texts = {}

    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                name = info.filename

                if name.endswith("/"):
                    continue

                name_lower = name.lower()

                if name.startswith("images/") and name_lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    base_name = os.path.basename(name)
                    tmp_img_path = os.path.join(work_dir, base_name)

                    with zf.open(info) as src, open(tmp_img_path, "wb") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)

                    images[name] = tmp_img_path

                if name.startswith("texts/") and name_lower.endswith((".txt", ".docx")):
                    with zf.open(info) as src:
                        txt_bytes = src.read()
                    texts[name] = txt_bytes

        for img_path, img_tmp_path in images.items():
            prefix = "_".join(Path(img_path).stem.split("_")[:-1])

            ref_text = ""
            for txt_path, txt_bytes in texts.items():
                if prefix in Path(txt_path).stem:
                    ref_text = extract_text(txt_bytes, Path(txt_path).suffix.lower())
                    break

            results.append((img_path, img_tmp_path, ref_text))

        if return_work_dir:
            return results, work_dir
        return results

    except Exception:
        # При ошибке cleanup делаем здесь, чтобы не оставлять мусор
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def extract_text(file_bytes: bytes, ext: str) -> str:
    ext = ext.lower()

    if ext == ".txt":
        return file_bytes.decode("utf-8", errors="ignore").strip()

    if ext == ".docx":
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())

    return ""
