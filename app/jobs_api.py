import base64
import datetime as dt
import json
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from google.cloud import firestore
from google.cloud import pubsub_v1
from google.cloud import storage

# --- Config (задано пользователем) ---
GCP_PROJECT_ID = "project-d245d8c8-8548-47d2-a04"
PUBSUB_TOPIC = "ocr-jobs"
UPLOAD_BUCKET = "ocr-checker-uploads-1018698441568"

# GCS layout
def job_gcs_path(job_id: str) -> str:
    return f"jobs/{job_id}/input.zip"


router = APIRouter()

db = firestore.Client(project=GCP_PROJECT_ID)
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(GCP_PROJECT_ID, PUBSUB_TOPIC)
gcs = storage.Client(project=GCP_PROJECT_ID)


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()


@router.post("/jobs")
async def create_job(zip_file: UploadFile = File(...)) -> Dict[str, Any]:
    if not zip_file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Минимальная валидация по имени/контент-тайпу (не идеальная, но лучше чем ничего)
    if not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip is supported for now")

    job_id = str(uuid.uuid4())
    gcs_object = job_gcs_path(job_id)
    gcs_uri = f"gs://{UPLOAD_BUCKET}/{gcs_object}"

    # 1) Создать job в Firestore
    db.collection("jobs").document(job_id).set(
        {
            "job_id": job_id,
            "status": "PENDING",
            "filename": zip_file.filename,
            "gcs_uri": gcs_uri,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "error": None,
            "result": None,
        }
    )

    # 2) Загрузить ZIP в GCS (стриминг чанками → без загрузки целиком в память)
    bucket = gcs.bucket(UPLOAD_BUCKET)
    blob = bucket.blob(gcs_object)

    # Важно: blob.open("wb") поддерживает потоковую запись
    with blob.open("wb") as f:
        while True:
            chunk = await zip_file.read(1024 * 1024)  # 1MB
            if not chunk:
                break
            f.write(chunk)

    # 3) Publish в Pub/Sub
    msg = {"job_id": job_id, "gcs_uri": gcs_uri}
    publisher.publish(topic_path, json.dumps(msg).encode("utf-8"))

    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    doc = db.collection("jobs").document(job_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Job not found")
    return doc.to_dict()  # формат согласован вами
