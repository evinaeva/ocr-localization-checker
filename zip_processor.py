import zipfile
import tempfile
import os
import shutil
from pathlib import Path
from typing import List, Tuple, Union, Optional, Dict, Any

from docx import Document
import io
import re


_LANG_RE = re.compile(r"\(([^)]+)\)\s*$")


def _extract_language_from_filename(filename: str) -> Optional[str]:
    """Extract language code from a filename stem that ends with '(xx)'.
    Examples:
      'Gold pop-up(en).docx' -> 'en'
      "Valentine's Day ... (13.02)(zh-Hans).docx" -> 'zh-Hans'
      'BM ... – IWD (en).docx' -> 'en'
    """
    stem = Path(filename).stem
    m = _LANG_RE.search(stem)
    return m.group(1) if m else None


def parse_zip_streaming(
    zip_path: str,
    *,
    return_work_dir: bool = False,
    return_extended: bool = False,
) -> Union[
    List[Tuple[str, str, str]],
    List[Tuple[str, str, str, Optional[bytes], str]],
    Tuple[List[Tuple[str, str, str]], str],
    Tuple[List[Tuple[str, str, str, Optional[bytes], str]], str],
]:
    """
    Parse ZIP and extract images into a temporary directory.

    Backward-compatible modes:
      - return_work_dir=False, return_extended=False: returns List[(img_path, img_tmp_path, ref_text)]
      - return_work_dir=True,  return_extended=False: returns (List[(...3)], work_dir)

    Extended mode (needed by OCR→section selection):
      - return_extended=True returns ref_bytes (original .docx bytes if available, else None)
        and language code extracted from reference filename if possible.
      - return_work_dir works the same: if True, returns (matches, work_dir).
    """
    work_dir = tempfile.mkdtemp(prefix="ocr_zip_")

    images: Dict[str, str] = {}
    texts: Dict[str, bytes] = {}  # path -> bytes

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
                        texts[name] = src.read()

        results_3: List[Tuple[str, str, str]] = []
        results_5: List[Tuple[str, str, str, Optional[bytes], str]] = []

        for img_path, img_tmp_path in images.items():
            prefix = "_".join(Path(img_path).stem.split("_")[:-1])

            ref_text = ""
            ref_bytes: Optional[bytes] = None
            language = "en"

            # Choose first matching reference file by stem inclusion (existing behavior)
            for txt_path, txt_bytes in texts.items():
                if prefix in Path(txt_path).stem:
                    ext = Path(txt_path).suffix.lower()
                    ref_text = extract_text(txt_bytes, ext)

                    # Only .docx bytes are useful for section extraction; keep None for .txt
                    if ext == ".docx":
                        ref_bytes = txt_bytes
                        lang = _extract_language_from_filename(txt_path)
                        if lang:
                            language = lang
                    break

            if return_extended:
                results_5.append((img_path, img_tmp_path, ref_text, ref_bytes, language))
            else:
                results_3.append((img_path, img_tmp_path, ref_text))

        if return_work_dir:
            return (results_5 if return_extended else results_3), work_dir
        return results_5 if return_extended else results_3

    except Exception:
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
