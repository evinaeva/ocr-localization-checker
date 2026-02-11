import base64
import json
import os
import tempfile

from fastapi import FastAPI, Request, HTTPException
from google.cloud import firestore
from google.cloud import storage

# Используем существующий парсер ZIP из вашего проекта
from zip_processor import parse_zip_streaming
from app.ocr import process_image

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
    print('PUBSUB_PUSH_BODY=' + json.dumps(body, ensure_ascii=False))

    # Pub/Sub push format: { "message": {"data": "base64..."}, "subscription": "..." }
    msg = body.get("message")
    if not msg or "data" not in msg:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message")

    payload = json.loads(base64.b64decode(msg["data"]).decode("utf-8"))
    job_id = payload["job_id"]
    gcs_uri = payload["gcs_uri"]

    _update_job(job_id, status="RUNNING", error=None)

    # скачать zip → temp file
    # gcs_uri: gs://bucket/path
    _, _, bucket_name, *obj_parts = gcs_uri.split("/")
    object_name = "/".join(obj_parts)

    tmp_zip = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_zip = tmp.name
            gcs.bucket(bucket_name).blob(object_name).download_to_file(tmp)

        # дальше ваша текущая логика parse_zip_streaming
        matches = parse_zip_streaming(tmp_zip)

        results = {}
        # ВАЖНО: тут пока пример — вы уже ограничивали до 10
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
            }

        _update_job(job_id, status="DONE", result={"results": results, "total": len(matches)})
        return {"ok": True}

    except Exception as e:
        _update_job(job_id, status="FAILED", error=str(e))
        return {"ok": True}  # для Pub/Sub важно вернуть 2xx, иначе будут ретраи
    finally:
        if tmp_zip and os.path.exists(tmp_zip):
            os.remove(tmp_zip)
