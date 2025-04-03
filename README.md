# tutor
AI Agents for Personalized Learning &amp; Tutoring

## Features
<table border="1" cellspacing="0" cellpadding="6">
  <thead>
    <tr>
      <th>Feature</th>
      <th>Status</th>
      <th>Comment</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>Student modeling</td><td>✅</td><td>Multiple stupdents supported</td></tr>
    <tr><td>Assess learning gaps and Assess knowledge retention</td><td>✅</td><td>Using quizzes</td></tr>
    <tr><td>Multiple AI tutors for Different subjects</td><td>✅</td><td>Using the same agent, but supports multiple subjects</td></tr>
    <tr><td>Different teaching styles</td><td>✅</td><td>Suport for textbook and podcast style</td></tr>
    <tr><td>Agents collaborate</td><td>✅</td><td>Study guides are asynchronously updated on every quiz answer</td></tr>
    <tr><td>Suggest interdisciplinary connections between topics</td><td>❌</td><td>Setup to update topic study guides, but LLM to recommend which study guides to update is not implemented</td></tr>
    <tr><td>Interactive exercises</td><td>✅</td><td>Selecting text in study guide allows to ask questions about the selected text</td></tr>
    <tr><td>Quizzes</td><td>✅</td><td></td></tr>
    <tr><td>Gamification elements</td><td>✅</td><td>Difficulty level grows with every question answered correctly. Or it falls if question is answered incorrectly. Agent decides when and by how much to increase the level of difficulty given all the questions answered so far </td></tr>
    <tr><td>Event-driven patterns</td><td>✅</td><td>Study Guide Agent sends quiz answers to --> Study Progress summarizes weaknesses and user proficiency level --> Study Guide Agent generates new study guide and quiz questions best on weaknesses and user proficiency level</td></tr>
    <tr><td>Agents maintain their state across events</td><td>✅</td><td>Using in memory persistence, but maybe should use a database if time allows</td></tr>
    <tr><td>Human interaction</td><td>❌</td><td>Need to add explanations on study guide and hints on quiz</td></tr>
    <tr><td>Integrate with existing process systems</td><td>✅</td><td>Pulling data from database to create study guide</td></tr>
    <tr><td>Ethical implications</td><td>❌</td><td>Need agents to double check errors or allow to report errors</td></tr>
  </tbody>
</table>


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

## Presentation

After clicking the link, click the downlaod button at the top right corner.
[Link to the presentation](./presentation/Tutor%20Agent%20Presentation.pptx)

## Architecture
![Architecture Diagram](images/flowchart.png)
