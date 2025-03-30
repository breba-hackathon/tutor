# tutor
AI Agents for Personalized Learning &amp; Tutoring

## Architecture
![Architecture Diagram](images/flowchart.png)

## Setup instructions
### Pre-requisites
Setup Kafka and run the server
```bash
docker pull apache/kafka:4.0.0
docker run -p 9092:9092 apache/kafka:4.0.0
```


Copy the .env.sample to .env, and then fill it out as you complete the instructions
```bash
cp .env.sample .env
```


```bash
gcloud config set project <PROJECT_ID>
```

```bash
export PROJECT_ID=$(gcloud config get project)
export SERVICE_ACCOUNT_NAME=$(gcloud compute project-info describe --format="value(defaultServiceAccount)")
```


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

Generate a service account key:
```bash
gcloud iam service-accounts keys create key.json \
  --iam-account=$SERVICE_ACCOUNT_NAME
``` 
