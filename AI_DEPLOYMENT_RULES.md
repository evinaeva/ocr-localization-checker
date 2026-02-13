AI Deployment Rules — Source of Truth

Core Rule



GitHub is the only source of truth for the application code.



All code changes MUST be made in the GitHub repository.

Application code or behavior must never be modified directly inside Google Cloud.



What counts as a change



This includes:



backend code (app/, worker/, shared/, zip\_processor.py)



UI (app/templates/)



Dockerfiles



requirements.txt



cloudbuild.yaml



OCR processing logic



Firestore / PubSub / Vision API handling



Strictly Forbidden



An AI agent must NOT:



edit files inside a running Cloud Run container



apply hot fixes via Cloud Shell or terminal



rebuild containers manually from local files



upload modified code to GCS



bypass the GitHub repository



Any direct code modification in GCP will be lost on the next deployment and is considered an error.



Correct workflow



Modify files in the GitHub repository



Commit the changes



Push to the deployment branch configured in Cloud Build (currently main)



Cloud Build automatically:



builds a Docker image



publishes it to Artifact Registry



deploys a new Cloud Run revision



Manual operational commands are allowed only for inspection, rollback, or traffic routing — not for introducing code changes.



Why this matters



Cloud Run executes immutable container images.



The running service comes from Docker images, not from server filesystem edits.



Direct code edits in GCP:



are not versioned



are not reproducible



disappear on redeploy



cause environment mismatch



Diagnostics (Allowed)



reading Cloud Run logs



inspecting Firestore / PubSub



checking revisions



switching traffic between revisions



Not allowed



Fixing production by changing code directly in Google Cloud.



If a problem is found



The agent must:



Identify the cause



Propose a code change in GitHub



Commit and push



Wait for Cloud Build deployment



Production must never be repaired without updating the repository.



Google Cloud is the runtime environment.

GitHub is the system of record.

