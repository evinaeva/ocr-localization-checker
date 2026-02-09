import zipfile
import io
from pathlib import Path
from typing import Dict, Tuple
from docx import Document

def parse_zip(zip_bytes: bytes) -> Dict[str, Tuple[bytes, str]]:
    """
    Парсит ZIP → {img_path: (image_bytes, reference_text)}
    banner_01_jp.png → ('banner_01_jp.png', 'Скидка 50%!')
    """
    matches = {}
    
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        images: Dict[str, bytes] = {}
        texts: Dict[str, bytes] = {}
        
        # Извлечение файлов
        for name in zf.namelist():
            if name.startswith('images/') and name.endswith(('.png', '.jpg')):
                images[name] = zf.read(name)
            if name.startswith('texts/') and name.endswith(('.txt', '.docx')):
                texts[name] = zf.read(name)
        
        # Matching по префиксу имени
        for img_path, img_bytes in images.items():
            prefix = '_'.join(Path(img_path).stem.split('_')[:-1])  # banner_01 из banner_01_jp
            
            ref_text = ""
            for txt_path, txt_bytes in texts.items():
                if prefix in Path(txt_path).stem:
                    ref_text = extract_text(txt_bytes, Path(txt_path).suffix)
                    break
            
            matches[img_path] = (img_bytes, ref_text)
    
    return matches

def extract_text(file_bytes: bytes, ext: str) -> str:
    if ext == '.txt':
        return file_bytes.decode('utf-8', errors='ignore').strip()
    if ext == '.docx':
        doc = Document(io.BytesIO(file_bytes))
        return '\n'.join(p.text.strip() for p in doc.paragraphs if p.text.strip())
    return ""
