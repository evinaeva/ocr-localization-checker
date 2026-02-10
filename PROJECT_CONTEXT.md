# Project Context – OCR Localization Checker

## Purpose and scope

**OCR Localization Checker** is an internal tool for the localization/QA team. It automates checking that the text appearing on marketing banners matches the expected translation. The system accepts image files (PNG/JPG) and, in future versions, ZIP archives with images and corresponding reference texts. For each image it must:

1. Extract text using a multi-layer OCR pipeline (Tesseract → PaddleOCR → Google Vision).
2. Compare the OCR result with a reference translation.
3. Report whether they match and highlight differences, and allow a human reviewer to override the result when necessary.

The goal is to reduce manual reading of localized banners and provide an objective pass/fail report for each image. The system must support multiple languages (currently: Japanese, Korean, Chinese, Hindi, Hebrew, Armenian, Kazakh, Arabic, English and Russian) and be extendable to others.

**Note:** Progress and current tasks should be tracked in `AI_PROGRESS.md`. This file describes the architecture and design principles, not day‑to‑day status.

## Modes of operation

There are two conceptual modes:

### Synchronous web service (current implementation)

- Handles **one image per HTTP request**. A user uploads a single PNG/JPG via a simple HTML form served by FastAPI.  
- The service immediately calls the OCR layer (currently Google Vision) and returns the recognized text in the response page.  
- This mode is appropriate for quick checks and small files. It is constrained by Cloud Run’s HTTP request/response lifecycle: the request must finish within `timeoutSeconds` and within the memory/CPU limits of a single container.  

### Batch processing (future design)

- For large numbers of images (e.g. a ZIP archive) or heavy OCR tasks, synchronous HTTP is not suitable. Cloud Run does not guarantee the container stays alive after a response is sent, and concurrency in a single process is limited by Python’s GIL.  
- Batch jobs must be offloaded to **asynchronous workers**, such as Cloud Run Jobs, Cloud Tasks with Pub/Sub triggers, or Cloud Functions. These workers can download the archive, process each image in turn, and write the results to a database.  
- The web service should only receive the archive, enqueue a task and return a job ID. A separate UI can later show progress and results.  
- Implementing this architecture requires explicit support in code and infrastructure; as of now it is **not implemented**.

## Infrastructure and components

- **Hosting:** Google Cloud Run in region europe‑west1.  
- **Container:** A Docker image based on `python:3.10-slim`. Deployed via CI/CD pipeline (GitHub → Cloud Build → Artifact Registry → Cloud Run). Only containerized deployment is supported; no on‑premises or desktop execution.  
- **Service account:** `ocr-service-account` used at runtime. It should have the minimal necessary roles (vision, storage, pubsub, sql/data access) but **should not** have `roles/run.admin`. Administrative deploy actions should be performed by a separate CI/CD account.  
- **CI/CD:** Cloud Build builds the Docker image and deploys to Cloud Run on every commit to the main branch. There is no staging environment or automated tests yet. In production this means any commit immediately goes live, which is risky. Future improvements should include staging, health checks, and test gates.  
- **Observability:** Logs go to Cloud Logging; metrics and traces are available through Cloud Monitoring/Trace. The service is stateless; no local storage persists between requests. Data that must persist (e.g. OCR results, review status) must be stored externally (Cloud SQL, Firestore or Cloud Storage).

## OCR strategy

A multi-layer OCR pipeline is planned:

1. **Layer 1 – Tesseract OCR:** A CPU‑bound open‑source OCR engine installed in the container. Suitable for simple cases; fast and free. It requires installing OS packages and language data.  
2. **Layer 2 – PaddleOCR:** A deep‑learning model providing higher accuracy on complex scripts. Integrating PaddleOCR will increase memory and disk footprint; note that models can be hundreds of megabytes and may require >1 GB RAM.  
3. **Layer 3 – Google Vision API:** Cloud OCR with broad language support. Used as a fallback or arbitrator when other engines disagree. Vision API offers `text_detection` and `document_text_detection`; the latter should be used for documents with multiple blocks or mixed languages.  

Currently only **Layer 3** is implemented, and it simply returns `text_annotations[0].description` (the aggregated text) from Vision API. This aggregated string loses layout information and may contain line breaks; for robust comparison you may need to normalise whitespace, punctuation and case. Automatic language detection in Vision is heuristic; it can misidentify text for languages like Japanese, Korean, Arabic and Hindi. Where possible, specify language hints or use `document_text_detection` to improve accuracy. It is unrealistic to guarantee 100 % exact match for all languages and fonts; human review is still necessary.

## Key limitations and risks

### Concurrency vs CPU

Cloud Run concurrency defines how many HTTP connections can be handled by a container at once, **not** how many OCR tasks run in parallel. A single container has 1 vCPU; Python code with heavy CPU operations (like image decoding or Tesseract) effectively runs one at a time due to the GIL. If concurrency is set high (e.g. 80), requests queue up and accumulate memory consumption, leading to out‑of‑memory (OOM) kills. In our tests, even a single 4k image can temporarily consume >300 MB due to Pillow decoding and Vision API serialization. Therefore, do not assume that 512 MB is sufficient; allocate 1 GB or more and set `concurrency` to a small number (1–10) for CPU‑bound OCR. For asynchronous batch jobs, use separate workers with appropriate resources.

### Memory and container limits

The default container limits (512 MiB, 1 vCPU) may be insufficient for multi‑layer OCR or large images. Peak memory usage includes image decoding, Vision API client serialization and Python overhead. When adding PaddleOCR or Tesseract, memory usage may exceed 1 GB. Adjust `memory` and `cpu` settings in `service.yaml` accordingly. Cloud Run will terminate a container immediately on OOM; there is no Python exception in that case.

### Statelessness and persistence

The Cloud Run service is stateless: it does not persist files or data between requests. Storing and presenting historical results or enabling human‑in‑the‑loop review requires an external database (Cloud SQL, Firestore or BigQuery) and storage (Cloud Storage). Without this, the UI cannot show history or allow marking results as correct/incorrect. Designing this data model is part of future work.

### Timeout and HTTP UX

Cloud Run enforces a maximum request duration of `timeoutSeconds` (currently 300 s), but many browsers, proxies or corporate networks will drop connections after 60–120 s. Users uploading large files risk seeing timeouts or incomplete responses. To avoid this, heavy work should be performed asynchronously with job IDs and polling; the synchronous web endpoint should validate input, enqueue the job and return quickly.

### Vision API consumption and language limitations

Vision API pricing is per **page**, not per file: a single PDF page or image counts as one unit. Retries and repeated calls also consume quota. The free tier provides ~1,000 pages per month; multi‑page documents or repeated testing can exceed this quickly. Always monitor usage. Automatic language detection is not infallible; to improve accuracy specify `languageHints` (e.g. `[\"ja\", \"ko\", \"ar\"]`) or use separate OCR engines per language.

### Security and IAM

- **Least privilege:** The runtime service account must not have administrative roles (e.g. `roles/run.admin`). Give it only what is needed: `roles/vision.user`, read/write on specific buckets, and read access to secrets. Use a different service account for deployment.  
- **Secrets management:** Store all credentials (e.g. Basic Auth passwords) in **Secret Manager** and mount them into the container via environment variables. Never hard‑code secrets in the code or configuration.  
- **Network and file validation:** Validate file size, content type and number of files on upload. Enforce limits on ZIP contents. Protect against ZIP bombs or malicious files by scanning or rejecting archives above a reasonable size.  

### CI/CD and deployment

Auto‑deploying every commit to production is convenient for prototyping but dangerous in production. Add a staging environment with smoke tests and manual approval before promoting to production. Implement unit tests and lints to catch errors early. Consider using GitHub Actions for additional checks before Cloud Build.

## Future improvements

Below are areas planned for development. Until implemented, treat them as **design goals**, not existing features.

- **ZIP archive support and batch processing:** Parse ZIP archives with image files and reference texts; enqueue a job for each archive; persist results and generate CSV/HTML summary reports. This must be implemented as an asynchronous pipeline using Cloud Run Jobs or Pub/Sub + Cloud Functions.  
- **Multi‑layer OCR:** Integrate Tesseract and PaddleOCR for cross‑validation; use Vision API only as arbitrator. Provide language hints and select the best result among engines.  
- **Exact matching and reporting:** Compare OCR output with reference translation (case‑sensitive, punctuation‑sensitive) and highlight differences. Support uploading reference texts in `.txt` or `.docx`.  
- **Manual review UI:** Add a page where a reviewer sees the reference and OCR text side by side, can mark it as correct or incorrect, leave a comment and update the status. Provide a progress dashboard for long tasks.  
- **Security enhancements:** Move secrets to Secret Manager; tighten IAM roles; disable unused APIs (BigQuery, Dataform etc.) unless actually needed.  
- **Scalability:** Offload heavy processing to background jobs and ensure each job has its own resource allocation (vCPU/memory). Use Pub/Sub for queues and Cloud Run Jobs for workers.  
- **Documentation:** Keep this `PROJECT_CONTEXT.md` and `AI_PROGRESS.md` updated with architectural changes, new services, limitations and the development roadmap.

## Recommendations for AI developers and maintainers

1. **Read this document and `AI_PROGRESS.md` before starting work.** Understand current architecture, goals and constraints.  
2. **Do not implement batch processing inside HTTP handlers.** Use asynchronous workers for anything that can exceed a few seconds or involve many images.  
3. **Check and install system dependencies (apt packages).** OCR engines like Tesseract and PaddleOCR require additional OS packages and models; update Dockerfile accordingly.  
4. **Pin library versions and update `requirements.txt`.** Use specific versions to ensure reproducibility.  
5. **Respect memory and CPU limits.** Test with realistic data; adjust Cloud Run settings; when adding heavy models, consider separate jobs or higher‑resource containers.  
6. **Store secrets securely.** Use Secret Manager or environment variables; never commit credentials.  
7. **Log and monitor.** Emit structured logs (JSON) for key events; record performance metrics (OCR duration, file size) for observability.  
8. **Add tests and staging before production deploys.** Each new feature should include tests; update this file when architecture changes.  
9. **When uncertain, ask.** If requirements are ambiguous, seek clarification rather than making assumptions.

---

This document represents the architectural context as of 10 Feb 2026. It is not a progress report; future development will expand functionality and adjust the architecture accordingly.
