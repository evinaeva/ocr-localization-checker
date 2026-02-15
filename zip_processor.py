import zipfile
import tempfile
import os
import shutil
from pathlib import Path
from typing import List, Tuple, Union, Optional, Dict
from docx import Document
import io
import re


# Language code: en, ru, he, pt-PT, zh-Hans, es-419, etc.
_LANG_TOKEN_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]+)*$", re.IGNORECASE)
_LANG_PARENS_RE = re.compile(r"\(([^)]+)\)\s*$")


def _extract_language_from_stem(stem: str) -> Optional[str]:
    """
    Try to extract language code from a filename stem using common patterns:
      1) trailing (...)  -> "file(zh-Hans)" => zh-Hans
      2) last token after separators -> "Banner_ru" / "Banner-ru" / "Banner ru" => ru
      3) stem itself is a lang code -> "ru" => ru
    Returns normalized lang token as it appears (case preserved minimally).
    """
    s = stem.strip()

    # 1) trailing parentheses token
    m = _LANG_PARENS_RE.search(s)
    if m:
        token = m.group(1).strip()
        if _LANG_TOKEN_RE.match(token):
            return token

    # 3) stem itself is a lang token (e.g., "ru", "he", "en", "zh-Hans")
    if _LANG_TOKEN_RE.match(s):
        return s

    # 2) last token after common separators
    # split by underscore, dash, space
    parts = re.split(r"[_\-\s]+", s)
    parts = [p for p in parts if p]
    if parts:
        token = parts[-1].strip()
        if _LANG_TOKEN_RE.match(token):
            return token

    return None


def _extract_language_from_filename(filename: str) -> Optional[str]:
    return _extract_language_from_stem(Path(filename).stem)


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

    Extended mode:
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

        # Build index of reference files by detected language (if any)
        texts_by_lang: Dict[str, List[str]] = {}
        for txt_path in texts.keys():
            lang = _extract_language_from_filename(txt_path)
            if lang:
                texts_by_lang.setdefault(lang, []).append(txt_path)

        results_3: List[Tuple[str, str, str]] = []
        results_5: List[Tuple[str, str, str, Optional[bytes], str]] = []

        for img_path, img_tmp_path in images.items():
            img_stem = Path(img_path).stem
            img_lang = _extract_language_from_stem(img_stem)

            ref_text = ""
            ref_bytes: Optional[bytes] = None
            language = img_lang or "en"

            chosen_txt_path: Optional[str] = None

            # 1) Try match by language first (handles cases like images/ru.jpg and texts/(ru).docx)
            if img_lang and img_lang in texts_by_lang:
                # Prefer .docx if multiple candidates
                candidates = texts_by_lang[img_lang]
                docx = [p for p in candidates if p.lower().endswith(".docx")]
                chosen_txt_path = sorted(docx or candidates)[0]

            # 2) Fallback to old prefix-match ONLY if we have a non-empty prefix
            if chosen_txt_path is None:
                prefix = "_".join(Path(img_path).stem.split("_")[:-1]).strip()
                if prefix:
                    for txt_path in texts.keys():
                        if prefix in Path(txt_path).stem:
                            chosen_txt_path = txt_path
                            break

            # 3) Final fallback: try exact stem containment (non-empty) to avoid matching everything
            if chosen_txt_path is None:
                if img_stem:
                    for txt_path in texts.keys():
                        if img_stem in Path(txt_path).stem:
                            chosen_txt_path = txt_path
                            break

            if chosen_txt_path is not None:
                txt_bytes = texts[chosen_txt_path]
                ext = Path(chosen_txt_path).suffix.lower()
                ref_text = extract_text(txt_bytes, ext)

                if ext == ".docx":
                    ref_bytes = txt_bytes

                # Prefer language from reference filename if present; otherwise keep img_lang/en
                lang_from_ref = _extract_language_from_filename(chosen_txt_path)
                if lang_from_ref:
                    language = lang_from_ref

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
