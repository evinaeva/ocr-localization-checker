import zipfile
import tempfile
import os
import shutil
from pathlib import Path
from typing import List, Tuple
<<<<<<< HEAD
from docx import Document
import io
=======
from io import BytesIO  # ← добавить
from docx import Document
>>>>>>> f5e11fa2298c861943e882b6f473103beec8d0eb


def parse_zip_streaming(zip_path: str) -> List[Tuple[str, str, str]]:
    results = []
    work_dir = tempfile.mkdtemp(prefix="ocr_zip_")

    images = {}
    texts = {}

    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                name = info.filename

                if name.endswith("/"):
                    continue

                if name.startswith("images/") and name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    base_name = os.path.basename(name)
                    tmp_img_path = os.path.join(work_dir, base_name)

                    with zf.open(info) as src, open(tmp_img_path, "wb") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)

                    images[name] = tmp_img_path

                if name.startswith("texts/") and name.lower().endswith((".txt", ".docx")):
                    with zf.open(info) as src:
                        txt_bytes = src.read()
                    texts[name] = txt_bytes

        for img_path, img_tmp_path in images.items():
            prefix = "_".join(Path(img_path).stem.split("_")[:-1])

            ref_text = ""
            for txt_path, txt_bytes in texts.items():
                if prefix in Path(txt_path).stem:
                    ref_text = extract_text(txt_bytes, Path(txt_path).suffix)
                    break

            results.append((img_path, img_tmp_path, ref_text))

        return results

    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def extract_text(file_bytes: bytes, ext: str) -> str:
    if ext == ".txt":
        return file_bytes.decode("utf-8", errors="ignore").strip()

    if ext == ".docx":
<<<<<<< HEAD
        doc = Document(io.BytesIO(file_bytes))
=======
        doc = Document(BytesIO(file_bytes))  # ← ключевое изменение
>>>>>>> f5e11fa2298c861943e882b6f473103beec8d0eb
        return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())

    return ""
