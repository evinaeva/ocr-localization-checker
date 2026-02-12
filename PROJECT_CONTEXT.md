________________________________________________________

Updates
________________________________________________________
PROJECT_CONTEXT — UPDATE 2026-02-12 (System operational; worker correctly serving Pub/Sub push)

Current confirmed architecture (unchanged):
User → Cloud Run ocr-checker → Pub/Sub ocr-jobs → push sub ocr-worker-push → Cloud Run ocr-worker → Firestore (Native)

Critical operational fact (resolved regression):

ocr-worker now runs the correct app (worker.main:app) and exposes /pubsub/push.

Validation:

Worker /openapi.json no longer matches checker (expected after fix)

POST /pubsub/push returns 400 Invalid Pub/Sub message for invalid payload, i.e., route exists.

Current production identifiers (factual):

Project: project-d245d8c8-8548-47d2-a04

Region: europe-west1

Worker URL: https://ocr-worker-1018698441568.europe-west1.run.app

Checker URL: https://ocr-checker-mgrzq6p2ga-ew.a.run.app

Active worker revision: ocr-worker-00012-bjb

Worker image: .../ocr-worker:workerfix-1770893776

Pinned tag: .../ocr-worker:prod-20260212

Verification evidence (factual):

Job processing confirmed twice:

d5a696a9-6977-49f6-b9ee-7280325e0754 → DONE

7284516b-8096-45b5-87c6-60d87e3fecd9 → DONE

Results include ocr, reference, and match: true.


# PROJECT_CONTEXT — UPDATE 2026-02-12 (Normalization deployed; PENDING regression)

## Confirmed architecture (unchanged)
User
→ Cloud Run `ocr-checker` (UI/API)
→ Pub/Sub topic `ocr-jobs`
→ Push subscription `ocr-worker-push`
→ Cloud Run `ocr-worker`
→ Firestore (Native)

Region: europe-west1
Artifact Registry: europe-north1
Project: project-d245d8c8-8548-47d2-a04

## Confirmed service endpoints (facts)
- ocr-checker URL:
  - https://ocr-checker-mgrzq6p2ga-ew.a.run.app
- ocr-worker URL:
  - https://ocr-worker-1018698441568.europe-west1.run.app

## API contract (facts)
- OpenAPI lists:
  - `POST /jobs`
  - `GET /jobs/{job_id}`
- `POST /jobs` expects multipart/form-data with required binary field:
  - `zip_file`

## Matching logic (implemented + deployed)
Goal: improve match quality without changing architecture.

### Implemented modules
- `worker/normalization.py`:
  - `normalize_strict(text)`
  - `normalize_soft(text)`
- Tests:
  - `tests/test_normalization.py`
  - `test_vectors/normalization_test_vectors.json`
- Local verification:
  - pytest passes (16 test vectors)

### Worker comparison changed
- In worker, match now computed as:
  - `normalize_strict(ocr_text) == normalize_strict(ref_text)`
(Previously was `strip()==strip()`.)

## Current production deployment (facts)
- `ocr-worker` deployed from image:
  - europe-north1-docker.pkg.dev/.../ocr-worker:latest
- Latest ready revision:
  - ocr-worker-00009-jj5
- Serving traffic:
  - 100% to latest

## Current system problem (facts)
A newly created job is stuck in PENDING:
- job_id: d5a696a9-6977-49f6-b9ee-7280325e0754
- GET /jobs/{job_id} returns:
  - status: PENDING
  - result: null
  - error: null
  - updated_at unchanged

This indicates the async step (Pub/Sub push → worker processing → Firestore update) is not completing for this job.

## Pub/Sub push configuration (facts)
Subscription `ocr-worker-push`:
- topic: projects/.../topics/ocr-jobs
- pushEndpoint: https://ocr-worker-.../pubsub/push
- ackDeadlineSeconds: 10
- deadLetterPolicy: false

## What is NOT yet confirmed (unknown; requires further checks)
- Whether push subscription uses OIDC token (pushConfig.oidcToken)
- Cloud Run invoker IAM bindings for ocr-worker (roles/run.invoker)
- Runtime service account of ocr-worker
- Whether worker push handler can return non-200 on valid Pub/Sub delivery

## Next diagnostics actions (must be executed as single-step commands)
1) Fetch subscription pushConfig to confirm OIDC/audience
2) Fetch ocr-worker IAM policy (getIamPolicy) to confirm invoker permissions
3) Fetch ocr-worker runtime serviceAccount from Cloud Run service spec
4) If IAM OK, review worker `/pubsub/push` handler code for validation-induced 4xx



PROJECT_CONTEXT — UPDATE 2026-02-11 (POST-FIX SYSTEM STATE)

Important: System state has materially changed.

The architecture is no longer under debugging.
The system has been verified working end-to-end in production.

Verified facts:

• Worker deployed with updated container image
• Pub/Sub push delivers successfully (HTTP 200)
• Firestore documents reach status DONE
• result.results contains OCR output
• UI renders OCR text and status correctly

Vision API

Earlier documentation mentioned:

"Vision API error: Request contains an invalid argument."

This is no longer an active issue.

Debug instrumentation confirmed:

• Valid image bytes are passed to vision.Image(content=...)
• Correct JPEG magic bytes detected
• OCR returns valid text

Conclusion:
Vision request construction is correct in current worker revision.

Frontend alignment

Earlier issue:
UI expected r.ocr_vision and r.status.

Current state:
UI template aligned with worker output:
    r.ocr
    r.match → PASS / MANUAL

Frontend and Firestore structure are now consistent.

Architectural status

The distributed asynchronous pipeline is confirmed operational:

API (Cloud Run)  
→ Pub/Sub topic  
→ Push subscription  
→ Worker (Cloud Run)  
→ Firestore  
→ UI render

No current infrastructure blockers exist.

Phase transition

Project has moved from:

"Cloud architecture validation"

to:

"Application logic refinement and production hardening".

Future improvements are incremental, not structural.





PROJECT_CONTEXT — UPDATE 2026-02-11 (system state verified)
Important: architecture status changed

The distributed pipeline is no longer hypothetical.
It has been observed working end-to-end in production.

A real job execution completed the full chain:

User upload → Cloud Storage → Pub/Sub push → Cloud Run worker → Google Vision → Firestore write

Observed facts:

• Pub/Sub push returned HTTP 200
• Worker processed the job
• Firestore document reached status: DONE
• updated_at changed after processing
• result object was written to Firestore

Conclusion:
Cloud Run, Pub/Sub, Firestore, IAM permissions, and async processing are operational.

This project is not currently blocked by infrastructure.

Worker runtime confirmation

Active worker revision is running a new container image:

image digest:
sha256:1823c8e4abefa4e42e3f7f545aa8bad2b1f885d28842dc5639b5058ef327385e

Container conditions:
Ready / Healthy / Active = succeeded

Therefore the system is executing real jobs on the updated worker.

Actual current failure class

The system now fails at the application layer, not the cloud layer.

Two concrete problems remain:

1. Google Vision request failure

Firestore result contains:

Vision API error: Request contains an invalid argument.

This indicates:
the worker successfully calls Vision API, but the request payload is malformed.

Possible areas:
• image bytes encoding
• content type
• empty/invalid image
• incorrect API request construction

This is currently the primary backend bug.

2. UI result rendering mismatch

Worker writes OCR output to Firestore at:

result.results[<image_path>].ocr

The UI does not display the OCR text even when the job is DONE.

Therefore:
the frontend template is reading a different field than the one written by the worker.

This is now the primary frontend bug.

Important behavioral model (now confirmed)

The worker is a stateless single-job processor:

one Pub/Sub push → one job → one Firestore update

No internal queue or polling loop exists.

Tooling constraint discovered

gcloud run ... commands are unreliable in this Cloud Shell environment
(they frequently crash with TypeError: string indices must be integers).

Service inspection must be done using the Cloud Run Admin REST API instead of gcloud CLI when necessary.

Phase transition of the project

The project has moved from:

“cloud deployment and async system debugging”

to:

“application logic debugging”

Remaining work is limited to:

fixing Vision API request construction

aligning UI template with Firestore result structure

__________________________________________________

First revision
__________________________________________________
OCR Localization Checker – Technical Context
and Architecture Document
Introduction
The OCR Localization Checker is a system designed to verify localized text in images or documents by
extracting visible text via OCR (Optical Character Recognition) and ensuring it matches the expected
locale. To handle potentially slow OCR operations without impacting user experience, the architecture is
built as a distributed, asynchronous pipeline. The design decouples the user-facing request from
background processing to maximize reliability, scalability, and clarity. Each component in this system
has a single well-defined responsibility, and robust error-handling mechanisms ensure consistent
behavior under failures, retries, or duplicate events.


System Architecture Overview
The system follows a distributed asynchronous architecture. A client initiates a check by sending an
image (or batch of images) to a web API. The request is not processed inline; instead, it is queued for
background processing. A dedicated worker service pulls tasks from the queue to perform OCR and
localization checks. Results are stored and later retrieved via the API. This approach isolates the quick
web request lifecycle from the longer OCR job lifecycle, ensuring the web service stays responsive while
heavy processing occurs in the background.


Key architectural components include: - API Service (Google Cloud Run) – Handles incoming HTTP
requests and delegates work to the background system. - Asynchronous Task Queue – Buffers and
dispatches jobs to workers, enabling reliable and at-least-once delivery with retry on failure. - Worker
Service (Cloud Run) – Performs the OCR and validation for each job asynchronously, updating the job
state and results. - Data Storage (Database/Storage) – Persists job states and results, enabling status
tracking, result retrieval, and idempotent processing.


This architecture ensures scalability (via auto-scaling of Cloud Run instances for concurrent jobs), fault
tolerance (through retry logic and state tracking), and clear data flow (each step has defined inputs/
outputs and triggers).


Components

API Service (Cloud Run)

The API Service is a stateless HTTP service running on Google Cloud Run. Its single responsibility is to
handle client requests and initiate OCR check jobs without performing the OCR itself. Key behaviors of
the API Service include:


     • Request Intake: Accepts client requests via an HTTP POST endpoint (e.g., POST /jobs ). The
       request contains one or multiple images (or document files) to check, along with any required
       metadata (such as target language or expected text, if applicable). The service supports both
       single-file and batch submissions in one request.




                                                    1
     • Input Validation: Immediately validates the request data:
     • Ensures at least one image/file is provided (reject with an error if missing).
     • Checks file format and size constraints (e.g., supported image types, size below a defined limit
       per file such as 5 MB each) to prevent unprocessable inputs.
     • If any validation fails, the API returns an HTTP 4xx error to the client and does not create a job.
     • Job ID Generation: For a valid request, generates a new Job ID (a unique identifier, e.g., a UUID).
       This ID will track the job through its lifecycle. The Job ID is used as an idempotency key to avoid
       duplicate processing and as a reference for result retrieval.
     • Job Record Initialization: Creates a new job record in the Data Storage with the Job ID, initial
       state (e.g., PENDING), and metadata:
     • Records the submission time and any relevant parameters (like target locale).
     • If the request is a batch of multiple images, the record notes the number of items and awaits
       results for all.
     • Task Queue Enqueue: Packages the job details into a task payload and enqueues it onto the
       Asynchronous Task Queue for processing by a worker:
     • The payload typically contains the Job ID and either the image data or a reference to where the
       image is stored (to avoid oversized messages). For large files, the API may first upload the
       content to a cloud storage location and include that reference in the task.
     • If multiple images are provided, the payload will include references to all images in the batch. (In
       more advanced implementations, the API could enqueue multiple tasks – one per image – but by
       default we use a single task per job for simplicity, as the worker can handle a batch internally.)
     • Confirms that the task was successfully queued. If the queue enqueue were to fail (e.g., queue
       service outage), the API would mark the job as FAILED and return an error. This ensures no
       request is accepted without actually being queued for processing.
     • Immediate Response: Returns an HTTP 202 Accepted response to the client with the Job ID (and
       perhaps a status URL):
     • The response indicates that the job has been accepted for processing asynchronously.
     • The client is expected to use the Job ID to poll for results or be notified when processing is
       complete (the system uses polling in this design; see result retrieval below).
     • The API does not wait for the OCR process to complete – it completes the HTTP request quickly
       (within a second or two) to remain responsive under load.

In summary, the API Service orchestrates the start of a job and provides the client with a reference, but
offloads the heavy lifting to the background worker. It strictly isolates the user request lifecycle from
the processing lifecycle.


Asynchronous Task Queue

The Task Queue is responsible for reliably dispatching OCR jobs to the Worker Service and handling
retry logic. This can be implemented using Google Cloud Tasks or Pub/Sub; the design works with
either. The Task Queue’s characteristics and responsibilities are:


     • Decoupling and Buffering: It acts as a buffer between the API and the Worker. Jobs pushed into
       the queue are stored until a Worker Service instance is available to process them. This smooths
       out traffic spikes and prevents the API from blocking on long tasks.
     • Trigger for Workers: Each queued task will trigger the Worker Service (e.g., via an HTTP push to
       a Cloud Run endpoint or a Pub/Sub subscription invocation). The task contains the necessary
       information for the worker to perform the job (Job ID and data references).
     • At-Least-Once Delivery: The queue ensures that every task will be delivered to a worker at
       least once. If a worker fails to acknowledge completion, the queue will retry the task




                                                    2
       automatically. This guarantees that no job is lost, though it introduces the possibility of a task
       being delivered more than once (which the worker must handle idempotently).
     • Retry and Backoff: Built-in retry logic handles transient failures:
     • If the Worker Service does not respond successfully (e.g., it crashes, times out, or returns an
       error), the queue will re-deliver the task after a delay. It uses exponential backoff between retries
       to avoid overwhelming the system. For example, it may wait a few seconds for the first retry,
       increasing for subsequent attempts.
     • A maximum retry limit is set (for instance, 3 attempts). This prevents endless reprocessing of a
       hopeless task. The retry policy (max attempts and backoff schedule) is configured based on
       expected transient failure scenarios.
     • Dead Letter Handling: If the task continues to fail after the maximum retries, it will be routed to
       a dead-letter mechanism:
     • For Cloud Tasks, this could be a separate dead-letter queue or an error log; for Pub/Sub, it could
       be a dead-letter topic.
     • The system will handle such cases by marking the associated job as FAILED since the
       background processing could not complete. (See Error Handling for how this is done – either the
       final worker attempt or a monitoring process will update the job status.)
     • Ordering and Parallelism: Each task is independent, so tasks may be processed out of original
       submission order if running in parallel. The queue does not guarantee strict ordering (especially
       if using Pub/Sub) – but since each job is separate, this is acceptable. Parallel processing is
       controlled by the number of worker instances.
     • Rate Control: The queue can throttle dispatch rate if needed (Cloud Tasks allows setting a rate
       limit, and Pub/Sub can be managed via subscriber flow control). This prevents flooding the
       Worker Service or external OCR API beyond their capacity. For example, we might configure the
       queue to only allow, say, 10 tasks per second to start, if the OCR API has a known QPS limit.

Overall, the Task Queue is the heartbeat of the asynchronous model, reliably handing off work to the
background workers and re-queuing if necessary. It abstracts the complexity of retries and ensures the
system can recover from transient issues without manual intervention.


Worker Service (Cloud Run)

The Worker Service is a Cloud Run service dedicated to processing OCR Localization jobs in the
background. It is triggered by incoming tasks from the queue. This service’s single responsibility is to
perform the OCR and localization-checking logic for a given job and record the outcome. Key aspects of
the Worker Service include:


     • Invocation Trigger: The worker is invoked automatically when a new task arrives from the
       queue. In a Cloud Run + Pub/Sub setup, for example, the Pub/Sub message is pushed as an
       HTTP request to the worker’s endpoint. In a Cloud Tasks setup, the task is delivered as an HTTP
       request to the worker’s URL. Each request to the worker corresponds to one job’s processing.
     • Task Payload Handling: On start, the worker receives the Job ID and data reference from the
       task payload:
     • It uses the Job ID to look up the job record in the Data Storage and confirm the current status.
       Normally it should find the job in PENDING state (or PROCESSING if a retry attempt where a
       previous worker died after marking processing).
     • If the job record is already marked SUCCEEDED or FAILED (meaning a previous attempt
       finished), the worker will recognize this as a duplicate delivery. In that case, it will not re-
       process the images. Instead, it will simply acknowledge the task and exit, ensuring idempotent
       behavior (no duplicate work). This check is critical for safe retry handling.




                                                    3
• If the job is still PENDING (expected for first attempt) or PROCESSING without completion
  (possible if a prior attempt crashed mid-way), the worker will proceed with processing. It updates
  the job status to PROCESSING (if not already) in the Data Storage as it begins actual work.
• OCR Processing: The worker performs the OCR and localization check on the provided image(s):
• Data Retrieval: If the image data was stored in cloud storage or a database, the worker fetches
  it using the reference. If the image was small and included directly in the task payload (e.g., as
  base64), it decodes it. This design avoids large payload issues by retrieving from storage when
  needed.
• OCR Execution: For each image in the job, the worker invokes an OCR engine to extract text:
        ◦ This could be an external API (such as Google Cloud Vision OCR) or a local library (such as
           Tesseract) packaged within the service container. The choice is abstracted in this context,
           but in either case the worker must handle it as an external call that might fail or take
           time.
        ◦ The worker calls the OCR function with appropriate parameters (e.g., language hints if
           relevant) and waits for the result. A timeout is enforced on each OCR call (for example, if
           no result within 30 seconds, the call is aborted and treated as a failure for that image).
           This prevents the worker from hanging indefinitely on one image.
        ◦ If the OCR call fails due to a transient error (network issue, service unavailability), the
           worker can retry the OCR call a few times internally (e.g., 3 retries with brief delays)
           before giving up on that image. This internal retry is separate from the queue retry and is
           meant for handling momentary issues quickly.
        ◦ If an OCR call returns an error indicating a permanent issue (e.g., image format not
           supported, or corrupted file), the worker will not retry that call further.
• Localization Check: After obtaining text results from OCR, the worker performs the localization
  verification:
        ◦ It checks the extracted text against the expected language or reference data. For
           example, it might verify that all extracted text is in the target language and flag any text
           that appears in a wrong language or remains untranslated.
        ◦ If reference strings or expected translations were provided, it compares the OCR text to
           those to find mismatches or missing translations.
        ◦ This step is domain-specific logic for the localization check. Any anomalies (e.g., English
           text found in a French-localized image) are recorded as errors or warnings in the results.
• Result Aggregation: The worker compiles the results for the job:
        ◦ For each image, it may store the extracted text and any localization issues found (e.g., a
           list of detected errors or a pass/fail outcome).
        ◦ If the job is a batch of images, results are collected for all images. The worker processes
           images sequentially by default. (If performance demands are high, this design could be
           extended to process images in parallel threads or spawn sub-tasks, but by default we
           keep it sequential within one worker invocation to simplify state handling.)
        ◦ If all images are processed successfully (OCR succeeded for each, even if some have
           localization issues, those issues are considered part of the result but not a processing
           failure), then the job as a whole is considered successful.
        ◦ If any image encounters a critical failure (e.g., OCR could not complete for that image
           even after retries), the worker considers the entire job as FAILED. Partial results for other
           images can be stored, but the overall status is failure since the requested task could not
           fully complete.
• Job Status Update: Once processing is done, the worker updates the Data Storage record for
  the job:
• If successful, mark status as SUCCEEDED, and attach the result data (extracted texts, check
  findings, etc.) to the job record.




                                                4
     • If failed (due to an unrecoverable error), mark status as FAILED, and record the error details
       (which image failed, what the error was, etc.). This helps users diagnose issues.
     • The update of status and results is atomic or done in a transaction if possible, to ensure
       consistency (so we don’t end up with a job marked succeeded with no results or similar).
     • Also record completion time for auditing and potential time-out detection.
     • Acknowledgement to Queue: Finally, the worker sends an appropriate response back to the
       queue system:
     • In a Cloud Tasks scenario, the worker would return an HTTP 200 response only after it has
       finished all work and updated the job status. This tells Cloud Tasks that the task is completed and
       can be removed from the queue.
     • If using Pub/Sub, the worker explicitly acknowledges the message after completing the work.
     • Important: The worker should only acknowledge (or return success) once it has safely recorded
       the outcome. This way, if the worker crashes or times out before finishing, the queue will not get
       an ack and will retry the task on another instance, ensuring the job eventually gets processed.
     • If the processing succeeded or hit a non-transient failure that we have handled (and marked in
       DB), the worker will still acknowledge as successful (so that the queue doesn’t retry again). Even
       for a job that ended in a FAILED state, once we’ve decided it’s a definitive failure (like a bad
       input), we consider the task done from the queue’s perspective.
     • If the worker itself runs into a condition where it cannot even update the job status (e.g., crashes
       mid-way or loses DB connection), it will not send a successful ack. In that case, the queue will
       assume the task failed and will retry it. The idempotency checks on Job ID will then come into
       play to prevent duplicating work when the next attempt happens.
     • Resource Cleanup: If any temporary files or data (like downloaded images) were created during
       processing, the worker cleans them up before completion to avoid resource leaks. Since Cloud
       Run instances can handle multiple tasks over their lifetime (unless scaled down), it’s important to
       free memory or temp storage after each task.

The Worker Service is designed for idempotent, fault-tolerant processing. It can safely be invoked
multiple times for the same job without side effects beyond the first successful completion. By strictly
updating the job state and results exactly once, and checking state at start, it ensures that duplicate
deliveries or concurrent attempts do not lead to double-processing or inconsistent data. The worker’s
concurrency is typically configured as one task per instance (Cloud Run concurrency setting = 1) to
dedicate the full CPU/memory to that OCR job and simplify threading, but the system as a whole can
scale out multiple instances to handle many jobs in parallel.


Data Storage (Job Store & Results Repository)

A persistent Data Storage component maintains the state and results of each job. This is typically a
database (for structured status data) and possibly a cloud storage bucket (for large blobs like images or
full OCR text outputs if too large for DB). It serves as the source of truth for job progress and outcomes.
Responsibilities and design of the data storage include:


     • Job Record Management: Each job has a record identified by the Job ID. The record holds:
     • Status – current state of the job (e.g., PENDING, PROCESSING, SUCCEEDED, FAILED).
     • Timestamps – submission time, start processing time, completion time.
     • Input metadata – e.g., number of images, target language, maybe original file names or
       references to where input files are stored if not directly included.
     • Result data – once completed, the extracted text for each image, and any localization check
       findings (such as error flags or summaries). If results are large, the record may contain pointers
       to files (for example, a JSON result file in cloud storage).




                                                    5
• Error info – if failed, an error message or code indicating the reason (timeout, OCR error, etc.,
  possibly including which image or step failed).
• Atomic Updates: The system updates the job record in well-defined stages:
• Initially, on job creation (by API) – inserts the record with status PENDING.
• When a worker starts processing – updates status to PROCESSING (and possibly a start time).
• On completion – updates status to SUCCEEDED or FAILED, writes the results or error details, and
  completion timestamp.
• These updates may be done using transactions or conditional operations to ensure that, for
  example, a duplicate worker doesn’t overwrite a completed job. We use the status as a guard:
  only update from PENDING to PROCESSING if it’s still in PENDING, etc.
• Concurrency Control: Only one worker should be updating a given job at a time. The
  application logic enforces this (since we check status at worker start). The DB can also enforce
  uniqueness of Job ID (primary key) and could use optimistic locking or similar to prevent
  conflicting updates. In practice, because of the idempotency design, concurrent writes for the
  same job are unlikely (duplicate tasks would detect the job is already being processed or done
  and exit).
• Idempotency Support: The data store is crucial for idempotency:
• The worker queries the job status to decide whether to proceed or abort (if already done).
• The presence of a completed record prevents redoing work. If a second attempt finds a
  SUCCEEDED status, it knows the first attempt finished the job, so it simply does nothing except
  acknowledge the queue.
• If a job is in PROCESSING state for a very long time (which might indicate a stuck or failed worker
  that didn't update to completed), that can be detected and handled (see Error Handling section
  for timeouts).
• Result Retrieval: The API Service uses the Data Storage to fetch job status and results when the
  client asks for it via an HTTP GET endpoint (e.g., GET /jobs/{JobID} ).
• When a client polls for the job, the API looks up the Job ID in the database.
• If found, it returns the status and (if available) results or error info.
• If not found (invalid ID), returns 404 Not Found.
• The results might be included directly in the JSON response, or provided as a link if they are large
  (for example, a link to download a detailed report).
• Storage of Inputs (if needed): If images/documents are large, the API/Worker might store them
  in a cloud storage bucket:
• The Data Storage (or job record) would then hold references (URIs or object IDs) to these files
  rather than raw binary.
• The worker uses those references to retrieve the files for processing.
• This ensures the system can handle large inputs and batch jobs without hitting message size
  limits or memory issues.
• After job completion, these input files could be deleted or retained for a period for debugging or
  audit. The design should specify a retention policy to avoid unbounded storage growth (e.g.,
  auto-delete stored images after 30 days).
• Security and Access: The data store is only accessible by the API and Worker services (not
  directly by end users). Proper authentication is in place between services to protect data. Job
  results might contain sensitive text (extracted from images), so the storage is secured and
  compliance with privacy requirements is considered (not detailed here, but implied).
• Scalability: The database can be a managed scalable DB (Cloud Firestore, Cloud SQL, etc.) to
  handle growing number of records. Access patterns are relatively simple: create, update status,
  read status/results. Index on status can be used if we implement a monitor for stuck jobs, etc.
  The storage is designed to handle concurrent requests from multiple workers and API instances.




                                               6
By maintaining all necessary state in a persistent store, the system avoids relying on in-memory or
instance-local data. This guarantees that even if services restart or scale dynamically, the job
information persists and can be accessed reliably.


End-to-End Workflow
Below is a step-by-step walkthrough of the entire process, from receiving a request to returning results,
covering both single-image and batch scenarios:


    1. Client Submits a Job: A client (or another service) initiates an OCR localization check by sending
       an HTTP POST request to the API Service (e.g., POST /jobs ). The request includes:
    2. The image or document file(s) to be checked. For multiple files, they can be sent as a list (for
       instance in a JSON payload or as form-data with multiple file fields).
    3. Any relevant parameters, such as the expected language of the text in those images, or perhaps
       reference translations (depending on the use case).
    4. Example (single file): { "image": "<base64-encoded image>", "language": "fr" }
       would request to check that the French image has no untranslated text.
    5. Example (batch):
        { "images": [ ...multiple image data... ], "language": "fr" } for checking a
       batch of images.
    6. API Validation and Acknowledgment: The API Service immediately validates the request:
    7. If validation fails (e.g., missing image data, too many images in one request exceeding a set
       limit, unsupported file type, etc.), the API responds with an error (HTTP 400) and the process
       ends here for this request.
    8. If valid, the API generates a Job ID and stores a new job record with status PENDING. It prepares
       the task payload (Job ID + input references).
    9. The API enqueues the job on the Task Queue. If enqueuing the task fails for any reason (rare, but
       if the queue service is down or misconfigured), the API would roll back the job record and return
       an error to the client (meaning the job did not start).
   10. On success, the API returns an HTTP 202 Accepted response. The response body contains the Job
       ID and a message like "Job accepted for processing", possibly along with a URL to check status
       (e.g., /jobs/<JobID> ).
   11. At this point, the client is free to disconnect; the heavy work will happen asynchronously. The
       Job is now in the queue awaiting a worker.
   12. Task Dispatched to Worker: The Task Queue delivers the job to the Worker Service:
   13. A Cloud Run instance for the Worker Service is invoked with the task payload. The platform may
       spin up a new container instance if needed (scaling up) or use an idle one.
   14. The payload includes identifiers to retrieve the images (either the images themselves if small, or
       pointers to cloud storage where the API uploaded them). For example, the payload might look
       like: { "jobId": "12345", "images": [ "gs://bucket/image1.png", "gs://bucket/
       image2.png" ], "language": "fr" } .
   15. The queue marks this task as in-progress and awaits a success signal (acknowledgment) from
       the worker.
   16. Worker Processing Begins: Upon receiving the task:
   17. The worker reads the Job ID and fetches the job record from the database. It confirms the job is
       PENDING. It then updates the status to PROCESSING with a timestamp (unless it was already
       marked processing by a previous attempt).
   18. The worker fetches each image file (from the payload or from storage URIs). It loads them into
       memory for analysis.




                                                    7
19. The worker then sequentially processes the images:
          1. Runs OCR on the image to extract text. If using an external OCR API, the worker sends the
             image data to that API and waits for a response. If using a local engine, it calls the OCR
             library locally.
          2. Waits up to a configured timeout (e.g., 30s) for the OCR result. If no result in time, it
             aborts that attempt. It may retry the OCR call a couple of times if it’s a transient issue.
          3. Once text is extracted, the worker analyzes the text for localization issues (e.g., checks if
             the text is in French or if any English words remain). It might use language detection or
             compare against expected text.
          4. Records the findings (e.g., “Image1: Found 2 English words that should be French” or
             “Image1: OK”).
          5. Moves to the next image and repeats the OCR and check.
20. If any image processing encounters a critical failure (e.g., the image is unreadable or the OCR
    API fails consistently), the worker decides to fail the job. It will stop processing remaining images
    (to save time, since the overall job cannot be fully successful) and mark the job as FAILED. (All
    partial results gathered so far will be preserved in the record for inspection, but the job outcome
    is failure.)
21. Completion of Processing: After processing all images (or encountering a fatal error), the
    worker finalizes the job:
22. If the job completed for all images without critical errors, it sets the job status to SUCCEEDED. It
    attaches the collection of OCR outputs and localization check results to the job record. For
    example, the result might include the extracted text for each image and a list of any issues
    found.
23. If the job failed (due to an error as described), it sets the job status to FAILED. It records which
    step failed and why (e.g., “Image2 OCR failed: network timeout” or “Image3 OCR failed: text not
    detectable”). This error info will be available to the client.
24. In both cases, it also logs the processing end time.
25. The worker then issues an acknowledgment to the queue (e.g., returns HTTP 200 if using push
    delivery), indicating this task is completed. At this moment, the queue knows it can remove this
    task from the queue.
26. The worker instance may then shut down or be kept alive by Cloud Run for a short period to
    handle another task if queued (Cloud Run might keep it warm), but it has no persistent state in
    memory between tasks.
27. Automatic Retry on Failure: If the worker crashes or times out before completing step 5 (for
    instance, if the container ran out of memory on a large image, or the Cloud Run instance
    exceeded its request time limit without responding):
28. The queue notices that the task was not acknowledged. After the worker’s invocation times out
    or returns an error status, the task remains or is re-enqueued.
29. After a delay, the Task Queue will dispatch the job to either a new instance or a restarted worker
    (this is transparent to the system).
30. The second attempt worker goes through the same steps. When it checks the job record at
    start, it might find status still at PROCESSING (if the first worker had updated it before crashing)
    or PENDING (if the crash happened before any update). In either case, since the job is not
    marked completed, the second attempt will proceed to process it.
31. Thanks to idempotent design, even if the first attempt had processed one of the images before
    crashing, the second attempt can safely reprocess that image. The system treats it as if starting
    fresh on the remaining work. The results from the second run will overwrite or supersede any
    partial data from the first if needed.
32. This retry process can happen multiple times, but typically there’s a configured limit (e.g., 3
    attempts). Each attempt will only finalize the job once; any duplicates after completion will detect
    the completed status and exit.




                                                  8
   33. Job Status Polling (Client): The client that submitted the job will likely poll for the result:
   34. The client calls GET /jobs/{JobID} on the API Service to check the job’s status. This can be
       done immediately and periodically (e.g., every few seconds) until a terminal state is reached.
   35. The API Service looks up the Job ID in the Data Storage. If the job exists:
           ◦ It returns a JSON response with at least the current status field. For example:
               {"jobId": "12345", "status": "PROCESSING"} while work is ongoing.
           ◦ If status is SUCCEEDED, the response will also include the results, for example:


                {
                  "jobId": "12345",
                  "status": "SUCCEEDED",
                  "results": [
                     { "image": "image1.png", "extractedText": "...", "issues":
                [ ... ] },
                     { "image": "image2.png", "extractedText": "...", "issues":
                [ ... ] }
                  ]
                }


             The exact structure may vary, but it contains all necessary output for the client to
             understand what text was found and any localization problems detected.
           ◦ If status is FAILED, the response will include error details:


                {
                    "jobId": "12345",
                    "status": "FAILED",
                    "error": "OCR processing failed on image2: network timeout"
                }


                (If partial results exist for other images, those might be included as well, or the error
                might indicate which part failed.)
   36. If the job is still processing, the client should continue polling later. If it’s completed (either
       succeeded or failed), the client can stop polling and use the result.
   37. If a Job ID is not found, the API returns 404, which could mean the ID was wrong or the job was
       purged.
   38. Result Delivery (Alternate mechanisms): While not implemented in this core design, it’s worth
       noting the architecture could support alternatives to polling:
   39. For instance, the client could supply a callback URL when submitting the job. The worker (or API)
       could POST the results to that URL upon completion. This decoupling allows easy integration
       with webhooks if needed in the future.
   40. Another approach is using a WebSocket or long polling to notify the client. These are optional
       and not included in the base specification, but the asynchronous nature of the system makes
       such extensions possible without fundamental changes.
   41. Job Completion and Cleanup: Once completed, the job remains in the Data Storage for
       retrieval. There may be a retention policy (e.g., results are kept for 7 days) after which old
       records are cleaned up to conserve space. Cleanup can be done by a scheduled process. This
       does not affect the processing flow but is part of operational maintenance.

Throughout this workflow, every state change and decision point is well-defined, ensuring two
independent implementations would follow the same sequence. The client always gets either a clear




                                                    9
accepted response with a job ID or an error; the background processes handle the rest, and the client
fetches the final outcome separately.


Job State Lifecycle
The job goes through a series of states from creation to completion. Defining these states and
transitions explicitly ensures completeness of the state machine and helps developers handle each
scenario consistently:


     • PENDING: Initial state after the job is accepted by the API and enqueued, but not yet started by
       a worker. The job record is created in PENDING as soon as the API enqueues the task. The job
       remains in this state in the queue until a worker begins processing it.
     • PROCESSING: Indicates a worker is actively working on the job. The transition from PENDING to
       PROCESSING occurs when a worker service instance picks up the task and starts execution. The
       worker sets the state to PROCESSING at the onset of its run (after confirming the job was in
       PENDING or if it was already set by a prior attempt).
     • SUCCEEDED: Terminal state for a job that has completed all processing successfully. Transition to
       SUCCEEDED happens when the worker finishes OCR and checks for all inputs without critical
       errors. The worker sets this state and stores the results. Once in SUCCEEDED, no further
       processing will be done on that job (any duplicate task deliveries will see the state and exit).
     • FAILED: Terminal state for a job that could not be completed due to an error. A transition to
       FAILED can happen in a few situations:
     • The worker encountered an unrecoverable error during processing (e.g., OCR failure after
       retries, invalid file content, etc.) and decided to abort the job. The worker updates the state to
       FAILED and notes the reason.
     • All retry attempts were exhausted without a successful completion. In this case, if the worker
       never got a chance to update (say it crashed each time before marking failed), a failure handler
       will mark the job as FAILED post-factum. This could be a final worker attempt detecting repeated
       failure or a separate monitoring process (see Error Handling below).
     • The API could also mark a job as FAILED if it cannot even enqueue it or if it detects some issue
       right after submission (though typically such a scenario would result in the job not being created
       at all, and an error returned to client instead).
     • CANCELLED: (Optional state, not implemented in the base flow.) If there were a feature to cancel
       a running job (not in current scope), a job could be marked CANCELLED. In this design, we
       assume no client-initiated cancellation; jobs run to completion or failure. For completeness, the
       design could accommodate a CANCELLED state if needed in future, where a running job would
       be signaled to stop. But since it's not part of the current requirements, we simply acknowledge it
       as a potential state and skip its implementation.

State Transitions: - Creation: NONE -> PENDING – When a new job record is created upon API
accepting a request. - Dispatch to Worker: PENDING -> PROCESSING – When a worker starts
processing the job. This might happen minutes or seconds after creation, depending on queue backlog.
- Success Completion: PROCESSING -> SUCCEEDED – When the worker finishes all tasks without
errors and commits the results. - Failure Completion: PROCESSING -> FAILED – When the worker
(or system) determines the job cannot complete successfully. Could happen mid-processing due to an
error, or after multiple failed attempts. - Cancellation: PROCESSING -> CANCELLED (not used
currently, would be triggered by an external cancel request if it existed). - Failure on Start: Edge case –
 PENDING -> FAILED if the job fails before processing begins (for example, if the queue fails to
deliver the task and we decide to mark it failed after max retries). Usually, the job would remain
PENDING until a worker tries it, but if no worker can ever start it, a timeout might eventually mark it
FAILED.




                                                    10
Each state has clear entry and exit conditions: - Enter PENDING upon job creation (exit PENDING when
taken by worker). - Enter PROCESSING when work starts (exit PROCESSING when work finishes or job
fails). - Enter SUCCEEDED or FAILED when job completes (terminal; no exit from these except deletion
after retention period). - We ensure that no job gets stuck indefinitely in PENDING or PROCESSING: - If
a job stays in PENDING too long (no worker picked it up due to some issue), that indicates a system
problem (workers not running or queue backlog). Operational alerts should catch that. Normally, Cloud
Run will auto-scale workers to empty the queue. - If a job stays in PROCESSING too long (e.g., a worker
hung or crashed without updating), we have a mechanism to resolve this (the queue retry or a
watchdog timer). - Thus, every job will eventually transition to either SUCCEEDED or FAILED, ensuring
completeness of the state flow.


The Job ID ties all these states together. It allows the API and worker to consistently refer to the same
job and update its state. Thanks to state tracking, the system can present a clear status to clients at any
time and handle duplicates safely by checking if a job is already done.


Error Handling and Reliability
The system is designed to be robust in the face of errors, with defined behaviors for timeouts and
retries at each stage. Below are the error handling strategies and how we ensure correctness and
idempotency under failure conditions:


     • API Level Errors:
     • Validation Errors: If the input is malformed or violates constraints (e.g., unsupported file type, file
       too large, missing mandatory parameters), the API returns a 400 Bad Request with an
       explanation. No job is created in these cases, so nothing persists or continues in the
       background.
     • Enqueue Failure: If, due to an unexpected outage or misconfiguration, the API cannot enqueue
       the task to the queue (for example, the queue service is down or returns an error), the API will
       mark the job as FAILED in the database immediately (or not create it at all) and return a 500/
       Internal Error to the client. This scenario is rare, but handling it prevents the client from thinking
       a job was accepted when it actually wasn’t queued.
     • The API itself is stateless and short-lived per request; it’s unlikely to encounter internal errors
       beyond validation and enqueue. If the API service crashes mid-request, the client would simply
       get no response or a 500, and they can retry the submission (which would create a new job; the
       original would either not exist or be incomplete. Since job creation either happens fully or not at
       all within one request, there's no partial state on API failure).
     • Worker Level Errors:
     • Transient OCR Errors: If the OCR engine call fails due to a network hiccup, temporary API outage,
       or similar, the worker will catch the exception or error code. It will retry the OCR call a limited
       number of times (e.g., 3 attempts with exponential backoff delays of 1s, 2s, 4s) within the same
       processing session. This handles intermittent issues quickly without involving the global task
       retry (which is heavier). During these retries, the job remains in PROCESSING and no external
       acknowledgment is sent yet.
     • Permanent OCR/Processing Errors: If an error is judged to be non-recoverable (e.g., "Invalid Image
       Format" from OCR, or after exhausting internal retries the call still fails), the worker will treat this
       as a job failure:
            ◦ The worker updates the job status to FAILED and records the reason (e.g., "OCR failed for
               image X: Unrecognized content").
            ◦ It then stops further processing of remaining images (because the job’s purpose was
               not fully achieved).




                                                     11
        ◦ The worker proceeds to acknowledge the task as completed (so the queue won’t retry). By
           doing this, we avoid retrying a job that is bound to fail again for the same reason.
• Exception or Crash: If the worker encounters an unexpected exception (bug in code, out-of-
  memory, etc.) and crashes or cannot complete:
        ◦ In this case, the worker might not get a chance to update the job status at all. The task
           will go unacknowledged.
        ◦ The Task Queue will interpret this as a failure and will retry the job on a new worker
           instance after a delay. The job remains in its last known state (perhaps still marked
           PENDING or PROCESSING from the first attempt).
        ◦ The new worker attempt will find the job record and continue processing. If the prior
           attempt had updated to PROCESSING, it stays in PROCESSING; otherwise the new worker
           will set it to PROCESSING.
        ◦ This automatic retry means the system self-heals from worker crashes. As long as the
           error is transient (maybe a fluke), the new attempt might succeed. If the crash happens
           consistently (due to a systemic bug or bad input that always crashes the worker), the
           retries will eventually exhaust.
• Handling Repeated Failures: If the same job crashes or fails multiple times in a row:
        ◦ After each failure (without acknowledgment), the queue delays and retries, up to the max
           attempts configured (say 3).
        ◦ If on the final attempt the worker still crashes or fails to complete, at that point we need
           to mark the job as FAILED. One way this can happen is if on the final attempt the worker
           catches the situation and marks FAILED before crashing again.
        ◦ If the worker never successfully runs to mark it, a monitoring mechanism takes over:
           either the Task Queue’s dead-letter system or a scheduled checker will identify that the
           job has not succeeded after max retries and mark it FAILED in the database.
        ◦ For example, if using Pub/Sub with dead-letter topic, a small Cloud Function could trigger
           on a dead-letter message and update the job status to FAILED with reason "Exceeded
           retry attempts". If using Cloud Tasks, since a task that fails max attempts is dropped, we
           could rely on a periodic audit (e.g., a cron job that finds jobs stuck in PROCESSING for
           longer than a threshold and marks them failed).
        ◦ This ensures no job remains endlessly in an undefined state. Every job will reach a
           terminal state (SUCCEEDED/FAILED) even in worst-case failure scenarios.
• Idempotency and Duplicate Prevention:
• The design explicitly uses the Job ID as an idempotency key. The worker checks the job state at
  start; if it finds the job already completed, it will not duplicate the work.
• The Data Storage operations (like “update to SUCCEEDED if currently PROCESSING”) help ensure
  that only one worker can complete the job. If two workers somehow processed in parallel (due
  to an odd timing of retries), one will succeed in updating status first and the other will see the
  status already changed and stop.
• All side effects (e.g., writing results, marking status) are tied to the Job ID, so a duplicate attempt
  won’t create a second separate record or overwrite a completed one incorrectly – it will detect a
  completed record and simply acknowledge the queue without altering data.
• External actions such as calling the OCR API are also effectively idempotent in impact – calling
  OCR twice just returns the same text; it doesn’t change state on the OCR service. So repeating it
  isn’t harmful aside from extra load, which we avoid unless needed.
• The one area to be careful is storing results: the worker should avoid, for example, appending to
  a results file multiple times. Our approach of replacing or writing results once when done avoids
  that. Using upsert or update operations in the DB rather than insert prevents duplicate entries.
• Timeouts:
• Worker Timeout: Cloud Run has a maximum request duration (commonly set to 15 minutes).
  We ensure jobs are designed to complete well within this. If a job is too large (e.g., hundreds of




                                                12
  images that can’t finish in time), that’s a design concern – we mitigate by setting job size limits or
  by splitting the workload (not implemented by default). If a worker does hit the Cloud Run
  timeout without responding, the platform will terminate it, leading to the task being retried on a
  new instance. The job then effectively gets another chance. We count on the retry mechanism to
  handle such cases, but also aim to avoid hitting this by design.
• OCR Call Timeout: Each OCR API call or library run has an application-level timeout (like 30
  seconds as mentioned). This ensures the worker doesn’t hang indefinitely on one image. If the
  OCR library itself hangs or is extremely slow, the worker will abandon that attempt. Repeated
  timeouts will lead to either trying again or failing the job if it seems persistent.
• Client Wait Timeout: From the client perspective, since they are polling, there isn’t a single open
  connection that times out. However, if a job is taking unusually long, the client might have its
  own timeout logic (deciding that after X minutes the result isn’t worth it). The system doesn’t
  automatically cancel jobs on slow processing, but the client can choose to stop polling. The job
  will still eventually finish on the backend.
• External API Failures & Rate Limits:
• If using an external OCR service, there could be rate limit errors if too many calls are made too
  quickly. The worker mitigates this by:
        ◦ Spacing out internal retries with backoff.
        ◦ The overall system can also limit how many workers run concurrently (via queue dispatch
            rate or Cloud Run max instances) to keep below known caps (for example, if the OCR API
            allows 10 QPS, we ensure not more than 10 images are OCRed per second globally).
        ◦ If an external API returns a specific error (like "Quota exceeded"), the worker can
            interpret that as a transient error and either wait a bit before retrying or fail the job with a
            clear message to the user to try later.
• Any exception from external services is caught so that the worker doesn’t just crash without
  updating state. Either it will handle it as described (retry or mark fail) or, if it’s an unforeseen
  exception, it would result in a worker crash which triggers the queue retry, as covered.
• Database Errors: If updating the job status or results in the Data Storage fails (e.g., network
  issue to the database):
• The worker will retry the database operation a few times if possible. It’s important to not lose the
  result after doing all the work. We could have a transient issue writing to the DB; the worker
  should hold the result in memory and attempt to write again shortly.
• If a database outage is prolonged and the worker cannot save the state, the worker may
  ultimately fail without acking. In this scenario, the task is retried later, meaning the entire job will
  be attempted again. This is not ideal, but due to idempotency the effect is just a delay (the
  second run will do the OCR again and hopefully succeed in saving results).
• We might implement a safeguard: if the worker completed OCR but can’t save results, perhaps
  do not mark as failed outright. Instead, let the retry happen and hopefully the DB is back by
  then. This is complex to signal, but effectively a crash/retry takes care of it implicitly.
• Logging and Monitoring:
• All components log key events: API logs job submissions and any validation errors; Worker logs
  when it starts a job, any errors per image, and when it completes or fails a job. These logs help in
  debugging and monitoring system health.
• Metrics can be collected: e.g., number of jobs processed, success/failure rates, average
  processing time, etc. If failure rates spike or processing time grows, it alerts engineers to
  investigate.
• A monitoring job or alert can watch for jobs stuck in PROCESSING for too long (beyond a
  threshold, like > 1 hour, which should not happen under normal circumstances) and raise an
  alarm or mark them failed as discussed.
• Client Error Cases:




                                                 13
      • If a client requests a status for a Job ID that doesn’t exist (or perhaps was already purged), the
        API returns a 404. This could happen if the client made a typo in the ID or if they waited too long
        and the job record was deleted. We document retention so clients know how long they have to
        fetch results.
      • If the client tries to submit a new job that is identical to a previous one quickly (e.g., resubmitting
        the same image by accident), the system will treat it as a separate job (with a new ID) unless we
        explicitly implement a deduplication check. Currently, no global dedupe across different
        submissions (only duplicates of the same job via retry are handled). We could note this as a
        potential extension if needed (to avoid reprocessing identical images twice within a short
        window), but that’s outside the core scope.

Through these mechanisms, the system achieves reliability and consistency: - It handles transient
failures gracefully with retries and doesn’t give up on a job at the first sign of trouble. - It avoids
infinite retry loops by capping attempts and failing cleanly when needed. - It guarantees idempotent
processing, so that duplicate deliveries or repeated actions do not cause confusion or double-counting.
- It ensures data integrity by updating job states in a controlled manner and using the database as the
single source of truth. - From the client’s perspective, they either get a result or a clear failure, with no
silent drop of requests.


Concurrency and Scaling Considerations
The OCR Localization Checker system is built to scale horizontally and handle multiple jobs concurrently,
while also controlling concurrency to protect resources and external services. Below are the
concurrency and scaling design points:


      • Cloud Run Auto-scaling: Both the API Service and Worker Service run on Cloud Run, which can
        automatically scale out new instances based on incoming load:
      • The API Service can handle many simultaneous requests by spinning up more instances (up to a
        configured max limit to control costs). Since the API work is lightweight (just enqueuing and
        responding), it can sustain high QPS from clients.
      • The Worker Service scales with the number of tasks in the queue. For example, if there are 50
        jobs waiting and each instance is limited to 1 task at a time, Cloud Run will create up to 50
        instances (again bounded by a max limit we configure, e.g., maybe 100 instances) to work on
        them in parallel. This means multiple OCR jobs can be processed at once, significantly improving
        throughput for batch processing or multiple users.
      • Single-Task Concurrency per Worker: Each Worker Service instance is configured to handle one
        task at a time (Concurrency = 1). This simplifies processing logic (no multi-threading needed in
        our code) and ensures that heavy OCR tasks don’t contend for CPU/memory on the same
        instance. It also means each job gets dedicated resources while it runs, which is important for
        performance consistency given OCR can be CPU-intensive.
      • If we wanted to increase throughput on a single instance, Cloud Run allows a higher concurrency
        (e.g., 5 tasks in parallel per instance), but we would then need to ensure the code can parallelize
        and the instance has enough resources. In our design, we choose simplicity and predictability by
        using one-at-a-time per instance.
      • Parallelism in Batch Jobs: For a single job that contains multiple images, our base
        implementation processes them sequentially within one worker instance. This is straightforward
        and avoids complicating result aggregation. However, it means the job’s total time will grow with
        each additional image. If a job with many images becomes too slow, there are strategies to
        improve this:
      • The system could spawn sub-tasks for each image (or small groups of images) to process in
        parallel. For example, upon receiving a batch of 20 images, the worker (or even the API) could




                                                      14
  create 20 sub-jobs internally, and wait for all to finish then combine results. This requires more
  complex coordination (a parent job waiting on child jobs).
• Alternatively, within one worker instance, multi-threading could be used to OCR multiple images
  concurrently if the instance has multiple CPU cores.
• These approaches introduce complexity and are optional optimizations. For consistency between
  engineers, our specification sticks to sequential processing per job by default, and suggests
  parallelizing batch items as a future enhancement when necessary.
• Rate Limiting External Calls: Concurrency is also managed with respect to the OCR engine:
• If using an external API with a known rate limit (say 10 requests per second), we must ensure the
  number of concurrent OCR calls doesn’t exceed that.
• With our design, if each worker handles one image at a time, and we allow N workers in parallel,
  we could potentially issue N OCR calls at once. We configure the max scale or the queue dispatch
  rate accordingly. For instance, if max instances = 50 and each could be calling OCR, that might be
  up to 50 QPS to the OCR API. If that’s too high, we either reduce max instances or implement a
  semaphore in the code to restrict simultaneous external calls.
• Another tactic is to batch multiple images into one OCR API call if the API supports it (some OCR
  services can process multi-page documents in one request). In our case, each image is separate
  unless dealing with multi-page PDFs.
• In summary, we avoid overwhelming external dependencies by tuning concurrency and possibly
  adding sleep/backoff if an external service responds with “too many requests” errors.
• Database Concurrency: The Data Storage can handle concurrent reads/writes for different jobs
  easily (especially if using a scalable NoSQL like Firestore or a properly indexed SQL DB). Each job
  is mostly independent. Contention on the same job record is minimal because normally one
  worker writes to it at a time. At worst, a duplicate worker might attempt an update at nearly the
  same time, which the database should handle either by last write wins or by an update check
  (e.g., only update if status was X).
• We ensure that writing results (which might be larger data) is efficient – possibly using a single
  upsert operation rather than many small writes.
• If results are large, writing to a separate storage (like uploading a file and storing the link in DB)
  means the DB write stays small (just the link), which is good for performance.
• Memory/CPU for OCR: Each worker needs sufficient memory and CPU to handle OCR. We
  choose an appropriate Cloud Run instance size (e.g., allocate enough CPU for the OCR library or
  to handle the image sizes we expect). If an image is extremely large (like a 50 megapixel photo),
  it could strain memory; we set practical limits on input size or downsize images if possible before
  processing.
• By scaling out horizontally, we handle multiple jobs concurrently rather than one job
  monopolizing an instance for too long. If one job is very large and slow, it will occupy one
  instance for a while, but other instances can still progress other jobs.
• Throughput vs. Latency Trade-offs: This system prioritizes throughput (ability to handle many
  jobs) and reliability over single-job latency. A single job might take several seconds to minutes to
  complete, depending on content and queue backlog, but many jobs can be processed in parallel.
  The asynchronous design inherently means a client doesn’t get results immediately, but it allows
  the system to scale and not time out the client.
• If near-real-time results were needed for a single image, one might opt for a synchronous path
  for small images. However, given OCR and especially localization checking might be involved,
  asynchronous is safer. Two engineers following this design would both implement the async
  pattern and therefore deliver similar performance characteristics.
• Limits and Configuration: We explicitly document and configure certain limits to avoid
  ambiguity:




                                               15
     • Max images per job request: e.g., 10 images. (This ensures one job doesn’t exceed time limits; a
       larger batch should be split by the client into multiple jobs or by future enhancements in the
       system.)
     • Max concurrent worker instances: e.g., 50. (Prevents runaway costs or hitting external API
       quotas. This can be adjusted based on load testing, but both engineers would at least set a
       limit.)
     • OCR API call rate limit: if known, incorporate that into the design as above (either throttle or
       restrict concurrency).
     • Cloud Run request timeout: set to a value that covers typical job sizes, e.g., 5 minutes per task. If
       a job may take longer, consider raising to the max 15 minutes or redesign job splitting. Both
       implementations should handle long jobs similarly.
     • Any deviation from these limits would be clearly documented to maintain consistency; for
       example, if Engineer A sets 10 images max and Engineer B unknowingly allows unlimited, their
       systems would behave differently. By specifying it here, we prevent that divergence.

This careful management of concurrency and scaling ensures the system can handle both single and
batch processing reliably: - Single image jobs will go through quickly, and many such jobs can be
processed in parallel. - Batch jobs will take longer for one job, but the system can still process different
batches concurrently on separate workers. The design supports both without changes to the core flow,
just differences in how many images a single job loops through. - The architecture prevents the scenario
where one slow job blocks others (thanks to queue and multiple workers), and it prevents overload by
using controlled parallelism and respecting external system limits.


Performance Considerations
In designing the OCR Localization Checker, we also account for performance and resource use to ensure
the system meets requirements without overutilization or bottlenecks. Key performance-related points
include:


     • Responsive API: The API Service returns control to the client quickly (usually within a second or
       two) by offloading processing. This means the end-user experience for job submission is fast.
       The trade-off is that they then wait for results out-of-band, but that is expected in an async
       model. The API’s work (generate ID, write DB entry, push queue) is lightweight and happens in
       milliseconds typically.
     • OCR Processing Time: OCR is the most time-consuming step. Its performance depends on:
     • The complexity and size of images (scanning a full page of text vs. a small screenshot).
     • The OCR engine used and whether it runs locally or as a remote API. A cloud OCR API might
       actually be faster if it uses powerful backend hardware, but includes network latency. A local
       library might be slower on CPU-bound tasks.
     • We expect a single image OCR to typically take on the order of a couple of seconds. We design
       timeouts generously but not too high (e.g., 30s) to cover worst cases (blurry image needing
       complex analysis) but to fail in reasonable time if it’s not returning.
     • For batch jobs, total processing time is roughly linear with the number of images (in the
       sequential design). So 5 images might take ~5x the single image time, give or take overhead.
     • Parallel Job Throughput: Because multiple worker instances can run, overall throughput is
       high. For example, if each job (single image) takes ~2 seconds, one instance handles 30 per
       minute. Ten instances could handle ~300 per minute, and so on. The system can scale out until
       some other factor (like external API quota or database write throughput) becomes the limiter.
     • Database Performance: Each job triggers a few database operations (insert, a couple of
       updates, and reads on polling). These are small and infrequent relative to OCR. Ensure the
       database is indexed by Job ID for fast lookup on polling. The volume of jobs per second is not




                                                    16
       enormous relative to what modern databases can handle (even a few hundred a minute is fine
       for Firestore or a decent SQL with indexes). We avoid heavy scans or joins, keeping operations
       keyed to job records.
     • Network and Data Transfer: If images are uploaded to the API and then stored or sent to
       workers:
     • We possibly transfer image data twice (client -> API, API -> storage, worker -> storage to fetch).
       This is the cost of decoupling, but it’s necessary for large files. Using storage means we aren’t
       holding large data in memory across services for long.
     • If images are small, the API can directly include them in the task to skip a storage round-trip,
       which saves time. The design allows either route depending on size.
     • Results data (text) is usually much smaller than images, so storing and sending results is not a
       bottleneck.
     • Time-Out and Job Limits: To keep performance within Cloud Run limits:
     • We recommended limiting each job to, say, 5-10 minutes of work at most. If a batch of images
       would take longer, consider splitting it. This ensures we don’t hit the Cloud Run max timeout
       often. Two engineers following this spec would enforce similar limits (e.g., by documentation or
       by code rejecting huge batches).
     • For instance, if one image takes ~5s to OCR, 100 images sequentially would take ~500s (~8.3
       minutes), which is near the default limit. So a sensible limit might be around 50 images per job
       to keep under ~5 minutes for average cases. This is somewhat arbitrary, but we explicitly
       mention it so the implementation will include such a check.
     • Memory Constraints: Processing high-resolution images can use a lot of memory. The worker
       container size is chosen to accommodate typical image sizes. We might downscale images if
       super high resolution isn’t needed for OCR, as an optimization. Both engineers would consider
       such optimization to avoid memory issues, since not doing so might cause an instance crash on
       huge inputs.
     • Cleanup and Resource Reuse: The system should clean up temporary data, as mentioned,
       which indirectly helps performance (freeing memory, not cluttering disk). Cloud Run instances
       can handle multiple tasks sequentially, so freeing resources after each ensures the next task has
       full capacity.
     • Monitoring Performance: We keep an eye on metrics like average job processing time and
       queue backlog length:
     • If jobs are backing up (queue length growing), it indicates we need to allow more concurrency or
       the tasks are too slow. Scaling up (increasing max instances) or optimizing OCR (maybe using
       faster OCR engine or adding GPU support if needed) would be solutions.
     • If the average job time suddenly spikes, there might be an issue with the OCR service or maybe a
       spate of particularly large documents; alerts can notify us to investigate.
     • Each engineer implementing this would include similar performance monitoring hooks to catch
       issues early.
     • Graceful Degradation: In case the external OCR service becomes very slow or unresponsive, the
       system will naturally slow down (as workers spend longer on each image). Clients might
       experience longer wait times. The system will still function (thanks to timeouts and retries) but
       performance is degraded. This is acceptable because correctness is maintained; however, in such
       cases, one might choose to inform users (via status or error messages) if things are unusually
       slow or suggest they try later. Not strictly part of the spec, but a possible user-experience
       consideration.

By articulating these performance considerations, we ensure the architecture is not only correct in
function but also practical in real-world usage. Both developers following this design will implement
similar limits and optimizations, leading to comparable performance profiles and avoiding any one
implementation being significantly less robust under load.




                                                  17
Conclusion
This document has presented a comprehensive, consistent architecture for the OCR Localization
Checker. Each component has a clear single responsibility, and all interactions are well-defined (from
triggers to data flow). The asynchronous design with Cloud Run and a task queue ensures the web
interface is responsive and that heavy OCR processing is handled reliably in the background. We
addressed potential failure modes with timeouts, retries, and idempotent logic so that the system
behaves predictably even under error conditions or repeated deliveries. All possible job states and
transitions are specified, leaving no undefined gaps — every job will deterministically end in either
success or failure, and clients can obtain a definitive result.


With support for both single and batch processing and careful consideration of concurrency and
performance, this architecture is scalable and adaptable. Two independent engineers implementing
this specification would arrive at the same system behavior and structure, given the explicit definitions
provided. The end result is a robust OCR Localization Checker service that is maintainable, fault-
tolerant, and aligned with best practices for distributed asynchronous processing.


## Обновления инфраструктуры (10 февраля 2026)

В рамках перехода к асинхронной архитектуре выполнены первоначальные настройки:

- **Firestore.** Создана база данных в режиме Native в регионе `europe‑west1`. Она будет использоваться для хранения статусов задач (Job) и результатов проверки. Firestore выбрана как хранилище, потому что проста в использовании и масштабируется под небольшие объёмы состояния.
- **Pub/Sub.** Создан топик `ocr‑jobs` в проекте `project-d245d8c8-8548-47d2-a04`. API‑сервис будет публиковать туда сообщения о новых заданиях, а отдельный воркер‑сервис будет подписываться на этот топик и выполнять обработку.

Эти изменения не затрагивают текущий сервис `ocr-checker`, но создают фундамент для новой схемы: **API → очередь → воркер → Firestore**.


                                                   18

