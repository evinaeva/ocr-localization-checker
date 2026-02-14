import base64
import json
import os
import tempfile
import shutil

from fastapi import FastAPI, Request, HTTPException
from google.cloud import firestore
from google.cloud import storage

from zip_processor import parse_zip_streaming
from app.ocr import process_image
from worker.normalization import normalize_strict, normalize_soft
from shared.docx_section_extractor import extract_section_candidates
from shared.reference_matcher import select_best_section

GCP_PROJECT_ID = "project-d245d8c8-8548-47d2-a04"
UPLOAD_BUCKET = "ocr-checker-uploads-1018698441568"

db = firestore.Client(project=GCP_PROJECT_ID)
gcs = storage.Client(project=GCP_PROJECT_ID)

app = FastAPI()


def _update_job(job_id: str, **fields):
    fields["updated_at"] = firestore.SERVER_TIMESTAMP
    db.collection("jobs").document(job_id).update(fields)


@app.post("/pubsub/push")
async def pubsub_push(request: Request):
    body = await request.json()
    print("PUBSUB_PUSH_BODY=" + json.dumps(body, ensure_ascii=False))

    msg = body.get("message")
    if not msg or "data" not in msg:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message")

    payload = json.loads(base64.b64decode(msg["data"]).decode("utf-8"))
    job_id = payload["job_id"]
    gcs_uri = payload["gcs_uri"]
    
    # Optional section hints from payload
    section_number = payload.get("section_number")
    section_name = payload.get("section_name")

    _update_job(job_id, status="RUNNING", error=None)

    # gcs_uri: gs://bucket/path
    _, _, bucket_name, *obj_parts = gcs_uri.split("/")
    object_name = "/".join(obj_parts)

    tmp_zip = None
    work_dir = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_zip = tmp.name
            gcs.bucket(bucket_name).blob(object_name).download_to_file(tmp)

        # Use extended mode to get ref_bytes and language
        matches, work_dir = parse_zip_streaming(tmp_zip, return_work_dir=True, return_extended=True)

        results = {}
        for img_path, img_file_path, ref_text, ref_bytes, language in list(matches)[:10]:
            with open(img_file_path, "rb") as f:
                img_bytes = f.read()

            # 1. Extract OCR text
            ocr_text = process_image(img_bytes)
            
            # Derive DOCX filename from img_path (texts/banner_01_(en).docx)
            # img_path format: "images/banner_01_(en).png"
            # ref_path format: "texts/banner_01_(en).docx"
            ref_path = img_path.replace("images/", "texts/").rsplit(".", 1)[0]
            # Try common extensions
            for ext in [".docx", ".txt"]:
                potential_ref = ref_path + ext
                # Check if this matches any key in original texts dict
                # Since we don't have direct access, use img_path stem as fallback
                break
            docx_filename = os.path.basename(ref_path + ".docx")
            
            # 2. Extract section candidates from reference DOCX
            candidates = []
            if ref_bytes and ref_bytes[:2] == b'PK':  # Check if it's a ZIP/DOCX
                try:
                    candidates = extract_section_candidates(ref_bytes, docx_filename, language)
                except Exception as e:
                    print(f"Warning: Failed to extract sections from {docx_filename}: {e}")
            
            # 3. Select best section
            if candidates:
                selection = select_best_section(
                    ocr_text=ocr_text,
                    candidates=candidates,
                    normalize_strict_fn=normalize_strict,
                    normalize_soft_fn=normalize_soft,
                    section_number=section_number,
                    section_name=section_name,
                )
                
                selected_ref_text = selection.chosen_text
                is_match = normalize_strict(ocr_text) == normalize_strict(selected_ref_text)
                
                results[img_path] = {
                    "image": img_path,
                    "reference": selected_ref_text,
                    "ocr": ocr_text,
                    "match": is_match,
                    "selection": selection.to_dict(),  # Add selection metadata
                }
            else:
                # Fallback to old behavior (full ref_text comparison)
                is_match = normalize_strict(ocr_text) == normalize_strict(ref_text)
                
                results[img_path] = {
                    "image": img_path,
                    "reference": ref_text,
                    "ocr": ocr_text,
                    "match": is_match,
                    "selection": {
                        "warnings": ["No candidates extracted, using full text"],
                        "manual_required": False,
                    },
                }

        _update_job(job_id, status="DONE", result={"results": results, "total": len(matches)})
        return {"ok": True}

    except Exception as e:
        _update_job(job_id, status="FAILED", error=str(e))
        return {"ok": True}  # Pub/Sub: важно вернуть 2xx, иначе будут ретраи
    finally:
        if tmp_zip and os.path.exists(tmp_zip):
            os.remove(tmp_zip)
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
