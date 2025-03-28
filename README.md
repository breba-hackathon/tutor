# tutor
AI Agents for Personalized Learning &amp; Tutoring

## Architecture
![Architecture Diagram](images/flowchart.png)

## Setup instructions

```bash
gcloud config set project <PROJECT_ID>
```

```bash
export PROJECT_ID=$(gcloud config get project)
export SERVICE_ACCOUNT_NAME=$(gcloud compute project-info describe --format="value(defaultServiceAccount)")
```

Enable Google Cloud APISs:
```bash
gcloud services enable compute.googleapis.com  \
                        aiplatform.googleapis.com \
                        secretmanager.googleapis.com \
                        cloudfunctions.googleapis.com
```

Setup Permissions:
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/secretmanager.secretAccessor"
```