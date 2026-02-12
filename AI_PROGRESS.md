____________________________________________________________________________

Updates
____________________________________________________________________________

AI_PROGRESS — UPDATE 2026-02-12 (worker fixed & pinned; checker deploy broken by merge markers; root cause identified)

A) Worker (ocr-worker) восстановлен и подтверждён E2E

Root cause прежних PENDING: ocr-worker обслуживал не тот FastAPI (эндпоинты совпадали с checker), поэтому /pubsub/push отдавал 404.

Исправление: в образе воркера исправлен запуск на worker.main:app (CMD uvicorn).

Подтверждение после фикса:

POST /pubsub/push на URL воркера возвращает 400 {"detail":"Invalid Pub/Sub message"} на {} — это ожидаемо для невалидного payload (маршрут существует).

Job’ы переходят в DONE и пишут результат (ocr, reference, match: true) — подтверждено минимум двумя job_id.

B) Фиксация рабочего воркер-билда в GCP (pin/release)

Текущий рабочий воркер-образ помечен тегом в Artifact Registry:

.../ocr-worker:prod-20260212 → тот же digest, что и ...:workerfix-1770893776.

Активная ревизия воркера на Cloud Run (на момент фиксации): ocr-worker-00012-bjb.

C) Регрессия: автодеплой checker (ocr-checker) начал падать после git push

Симптом (Cloud Build step gcloud run deploy ocr-checker):
The user-provided container failed to start and listen on PORT=8080.

Root cause найден по логам ревизии: контейнер падает при старте из-за SyntaxError в zip_processor.py:

в файле остались merge-маркеры <<<<<<< HEAD ... ======= ... >>>>>>>, из-за чего импорт zip_processor ломается, и uvicorn не поднимает приложение.

Следствие: Cloud Run health check не проходит → деплой ocr-checker фейлится, хотя docker build/push успешны.

D) Текущее действие для устранения регрессии (what to commit)

В репозитории нужно убрать merge-маркеры и оставить рабочий код zip_processor.py (вариант без маркеров, компилируется python -m py_compile).

После коммита фикса — ожидается, что Cloud Build триггер снова сможет задеплоить ocr-checker.


AI_PROGRESS — UPDATE 2026-02-12 (PENDING fixed; worker restored; release pinned)

What was fixed (root cause, factual):

Jobs stuck in PENDING were caused by ocr-worker serving the checker API instead of the worker handler.

Evidence:

POST /pubsub/push on worker URL returned 404 Not Found

openapi.json on worker URL exposed ['/', '/jobs', '/jobs/{job_id}'] (same as checker)

Fix applied (factual):

Dockerfile corrected to run worker app:

from CMD ["uvicorn","app.main:app", ...]

to CMD ["uvicorn","worker.main:app", ...]

New image built and deployed:

Cloud Run ocr-worker revision now: ocr-worker-00012-bjb

Image: .../ocr-worker:workerfix-1770893776

Worker endpoint now exists:

POST /pubsub/push returns 400 {"detail":"Invalid Pub/Sub message"} for {} (expected for invalid payload)

End-to-end verification (factual):

Previously stuck job moved to DONE with match: true:

job_id d5a696a9-6977-49f6-b9ee-7280325e0754

New independent job also completed immediately:

job_id 7284516b-8096-45b5-87c6-60d87e3fecd9

Both jobs produced result.results[...].ocr and match: true.

Release pinning in Google Cloud (factual):

Artifact Registry tag added:

.../ocr-worker:prod-20260212 points to the same image as workerfix-1770893776.

Git status (partly factual):

Local commits created:

release commit + merge commit (conflict resolved in zip_processor.py).

GitHub push: не знаю (в этом чате нет вывода успешного git push после merge).



# AI_PROGRESS — UPDATE 2026-02-12 (Normalization deployed; job stuck in PENDING)

## What was completed (facts)

### A) Matching logic improvement (worker)
- Implemented strict/soft normalization module:
  - `worker/normalization.py` with:
    - `normalize_strict(text)`
    - `normalize_soft(text)`
- Added local test vectors snapshot:
  - `test_vectors/normalization_test_vectors.json`
- Added unit tests:
  - `tests/test_normalization.py`
- Local tests confirmed:
  - `python3 -m pytest -q` → **16 passed**

### B) Worker matching now uses normalize_strict
- In `worker/main.py`:
  - Added import: `from worker.normalization import normalize_strict`
  - Replaced comparison:
    - from: `ocr_text.strip() == ref_text.strip()`
    - to: `normalize_strict(ocr_text) == normalize_strict(ref_text)`
- Sanity check confirmed:
  - `python3 -m py_compile worker/main.py` → OK

### C) Deployment: ocr-worker updated
- Confirmed current image in Cloud Run before deploy:
  - `europe-north1-docker.pkg.dev/.../ocr-worker:latest`
- Cloud Build:
  - First attempt failed due to wrong build context (used `./worker`): Dockerfile expected `worker/requirements.txt`.
  - Fixed by building from repo root:
    - `gcloud builds submit --tag europe-north1-docker.pkg.dev/.../ocr-worker:latest .`
- Cloud Run deploy succeeded:
  - `gcloud run deploy ocr-worker --region europe-west1 --image .../ocr-worker:latest`
- Current serving revision:
  - **ocr-worker-00009-jj5** serving 100% traffic
- Verified via Cloud Run Admin REST:
  - `latestReadyRevision` points to **ocr-worker-00009-jj5**
  - (Traffic field may show empty revision with 100% for “latest”)

### D) Verification tooling
- Confirmed ocr-checker URL via Cloud Run Admin REST:
  - `https://ocr-checker-mgrzq6p2ga-ew.a.run.app`
- Confirmed OpenAPI:
  - Endpoints: `/jobs`, `/jobs/{job_id}`, `/`
  - POST `/jobs` uses multipart/form-data with required field **`zip_file`**

## Current issue (regression / unverified)
### Jobs remain stuck in PENDING
- Created a minimal test ZIP in Cloud Shell (`strict_test.zip`):
  - `texts/test_en.txt`: `Hello World\nFrom OCR`
  - `images/test_en.png` uploaded by user
- Job created successfully:
  - POST `/jobs` returned job_id: `d5a696a9-6977-49f6-b9ee-7280325e0754`
- But GET `/jobs/{job_id}` remains:
  - `status: PENDING`
  - `result: null`
  - `error: null`
  - `updated_at` unchanged

## Pub/Sub delivery checks (facts)
- Subscription exists and points to worker:
  - subscription: `ocr-worker-push`
  - topic: `ocr-jobs`
  - pushEndpoint: `https://ocr-worker-1018698441568.europe-west1.run.app/pubsub/push`
  - ackDeadlineSeconds: 10
  - deadLetterPolicy: false

## Hypothesis to validate next (needs factual checks)
Most likely causes now:
1) Cloud Run invoker IAM / authentication mismatch (Pub/Sub push receiving 401/403)
2) Worker push handler returning non-200 due to request validation (even if IAM OK)
3) Publish from ocr-checker not actually happening (less likely given job stays PENDING, needs code inspection)

## Next concrete steps (do not batch; one command per step)
1) Inspect subscription pushConfig for OIDC settings (oidcToken/audience)
2) Inspect Cloud Run ocr-worker IAM policy (roles/run.invoker bindings)
3) Inspect Cloud Run ocr-worker runtime service account
4) If IAM OK: inspect worker `/pubsub/push` handler code for 4xx paths

## Known constraint
- Cloud Build SA cannot write Cloud Logging (roles/logging.logWriter missing). This is informational; builds still succeed.


AI_PROGRESS — UPDATE 2026-02-11 (POST-FIX STATE)

System status has changed again. Previous notes about Vision API failure and UI mismatch are no longer accurate.

What is now proven (current production state)

1. Vision OCR is operational

The worker processes real JPEG images successfully.
Debug fields confirm:

• bytes_len > 0
• correct JPEG magic bytes (ffd8ffe1…)
• fmt_guess = jpeg
• OCR text is returned by Google Vision

Therefore:
The "Vision API error: Request contains an invalid argument" issue was not systemic.
It was related to an earlier worker revision and is resolved.

2. UI rendering mismatch is fixed

The template previously expected:
    r.ocr_vision
    r.status

The worker writes:
    r.ocr
    r.match

Template updated to:
    {{ r.ocr }}
    PASS / MANUAL derived from match

OCR column and Status column now render correctly in production.

3. End-to-end pipeline fully confirmed

Observed working chain:

ZIP upload → Cloud Storage → Pub/Sub push → Cloud Run worker
→ Vision OCR → Firestore write → UI render

Firestore evidence:
• status = DONE
• updated_at updated
• result.results populated
• _debug entries present
• OCR text visible in UI

Conclusion:
Infrastructure + application logic both functioning.

Current project phase

The project has transitioned from:

"debugging distributed cloud system"

to:

"stabilization and quality improvements"

Remaining work is no longer about infrastructure.

Next focus areas (application-level improvements):

• Improve OCR/reference matching logic (currently strict == comparison)
• Add normalization (whitespace, punctuation, case, hyphenation)
• Remove _debug block from production worker
• Optional: implement idempotency guard (skip if DONE)
• Optional: refine retry strategy for transient Vision errors




AI_PROGRESS update (2026-02-11, addendum — factual corrections)

Important clarification of current real system state

The EasyOCR cleanup described above is correct, however the operational status of the system has changed and must be updated.

What is now proven

Worker is already deployed with a new image

Active Cloud Run revision changed.

Running image digest: sha256:1823c8e4abefa4e42e3f7f545aa8bad2b1f885d28842dc5639b5058ef327385e

Revision conditions: Ready/Healthy = succeeded.

Therefore production is no longer running the pre-cleanup worker.

End-to-end pipeline is confirmed working

The following chain has been observed to complete successfully:

Upload ZIP → Cloud Storage → Pub/Sub push → Cloud Run worker → Vision OCR → Firestore update

Evidence:

Firestore document reaches status: DONE

updated_at changes after processing

result object is written

Pub/Sub push returns HTTP 200

Conclusion:
Infrastructure (Cloud Run, Pub/Sub, Firestore, Storage, async processing) is operational.

Current failures are NOT infrastructure-related

The system is no longer blocked by:

deployment

Pub/Sub delivery

permissions

container crashes

The remaining problems are application-level.

Actual current issues

1) Vision API error
Firestore contains:
"Vision API error: Request contains an invalid argument."

This indicates a problem in:

image bytes preparation OR

Vision request construction.

2) UI rendering mismatch
Worker writes OCR output to:

result.results[image].ocr

The UI does not display it yet, meaning the template is reading a different field.

Clarification about repository state

The repository on GitHub still contains old code.
The cleanup exists only in the Cloud Shell working directory and exported archive.

The earlier grep verification applies to the workspace copy, not the remote repository.

Tooling constraint discovered

gcloud run ... commands are unreliable in this Cloud Shell environment (frequent TypeError crashes).
Service state must be inspected via Cloud Run Admin REST API instead.

Project phase change

The project has transitioned from:

“distributed system deployment/debugging”

to:

“application logic debugging (Vision request + UI data binding)”.

Next work should focus on:

fixing the Vision API request

aligning UI with Firestore result structure
апдейт 10.02
## Что уже работает
- Рабочий деплой на Cloud Run.
- Автоматический пайплайн GitHub → Cloud Build → Cloud Run.
- OCR через Google Vision для одиночного изображения.
- Веб‑форма загрузки.
- ✅ **Создана база Firestore (Native mode) в регионе europe‑west1 для хранения статусов заданий.**
- ✅ **Создан топик Pub/Sub `ocr‑jobs` для постановки задач в очередь.**

## Последняя выполненная задача
Настроена инфраструктура: создана Firestore (native mode) и топик Pub/Sub `ocr‑jobs`.

## Текущая задача (не повторять предыдущее!)
- Реализовать API‑эндпоинты для создания Job и публикации задания в Pub/Sub.
- Разработать воркер‑сервис, который подписывается на `ocr‑jobs`, выполняет OCR и обновляет статус в Firestore.

## Следующие задачи (приоритет снижается сверху вниз)
1. Извлечение текста из TXT/DOCX.
2. Сравнение строк на полное совпадение.
3. Таблица результатов в UI.
4. Режим ручной проверки.

✅ Добавлены API endpoints: POST /jobs (создаёт job, грузит ZIP в GCS, публикует Pub/Sub), GET /jobs/{job_id} (читает Firestore)
“Как задеплоить worker” (без выполнения):

build: gcloud builds submit --tag ...

deploy: gcloud run deploy ocr-worker ...

subscription push: gcloud pubsub subscriptions create ... --push-endpoint=https://.../pubsub/push


____________________________________________________________________________

First revision
____________________________________________________________________________
# AI Progress Log

## Current Phase
Phase 1 — Core Validation (ZIP upload and text matching)

## What already works
- Cloud Run deployment successful
- Automatic deploy via GitHub → Cloud Build → Artifact Registry → Cloud Run
- Single image OCR using Google Vision
- Web upload form available

## Known problems
- No ZIP archive support yet
- No reference text extraction
- No comparison report
- No manual review UI

## Last completed task
Google Vision OCR integrated and returning text.

## Current task (DO NOT REPEAT PREVIOUS WORK)
Implement ZIP archive processing:
- Read images from /images
- Read reference texts from /texts
- Match files by filename prefix

## Next tasks (priority order)
1. Extract reference text from TXT/DOCX
2. Exact match comparison
3. Result table in UI
4. Manual review mode

## Rules for AI developer
- Never rewrite existing working OCR
- Modify minimal files
- Prefer adding modules instead of replacing main.py
- After completing a task: update this file


