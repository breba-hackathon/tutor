import asyncio
import json
import threading
import time
from typing import List

import aiohttp
from kafka import KafkaConsumer, KafkaProducer
from pydantic import BaseModel

# Constants
KAFKA_BROKER = 'localhost:9092'
STUDY_PROGRESS_TOPIC = 'study_progress'
QUIZ_QUESTION_TOPIC = 'quiz_question'

_topics = [STUDY_PROGRESS_TOPIC, QUIZ_QUESTION_TOPIC]

# Global subscriber list
_subscribers: dict[str, List[str]] = {}

# Kafka Producer
_producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)


class StudyProgressEvent(BaseModel):
    username: str
    subject: str
    topic: str
    update: str


class QuizQuestionEvent(BaseModel):
    username: str
    subject: str
    topic: str
    quiz_question: str


def start_pub_sub_consumer():
    """
    Start the consumer in a background thread.
    """
    t = threading.Thread(target=_start_async_consumer, daemon=True)
    t.start()


def listen_to_study_progress(endpoint: str) -> None:
    """
    Register an endpoint to receive updates from the STUDY_PROGRESS_TOPIC.
    """
    if endpoint not in _subscribers:
        # Get or Initialize the list of subscribers for this topic and append endpoint
        _subscribers.setdefault(STUDY_PROGRESS_TOPIC, []).append(endpoint)


def update_study_progress(event: StudyProgressEvent) -> None:
    """
    Publish a new event to the 'study_progress' Kafka topic.
    """
    _producer.send(STUDY_PROGRESS_TOPIC, event.model_dump())
    _producer.flush()


def listen_to_quiz_question(endpoint: str) -> None:
    """
    Register an endpoint to receive updates from the QUIZ_QUESTION_TOPIC.
    """
    if endpoint not in _subscribers:
        # Get or Initialize the list of subscribers for this topic and append endpoint
        _subscribers.setdefault(QUIZ_QUESTION_TOPIC, []).append(endpoint)


def update_quiz_question(event: QuizQuestionEvent) -> None:
    """
    Publish a new event to the 'study_progress' Kafka topic.
    """
    _producer.send(QUIZ_QUESTION_TOPIC, event.model_dump())
    _producer.flush()


def _start_async_consumer():
    asyncio.run(_consume_and_forward_async())


async def _consume_and_forward_async():
    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='study_progress_forwarder'
    )
    consumer.subscribe(topics=_topics)

    async with aiohttp.ClientSession() as session:
        for msg in consumer:
            event = msg.value
            subscribers = _subscribers.get(msg.topic, [])
            tasks = [
                _post_event(session, endpoint, event)
                for endpoint in subscribers
            ]
            await asyncio.gather(*tasks)


async def _post_event(session: aiohttp.ClientSession, endpoint: str, event: dict):
    try:
        async with session.post(endpoint, json=event, timeout=30) as resp:
            if resp.status != 200:
                print(f"Failed to post to {endpoint}, status code: {resp.status}")
            else:
                response_text = await resp.text()
                print(f"Successfully posted to {endpoint}, {response_text}")
    except Exception as e:
        print(f"Failed to post to {endpoint}: {e}")


if __name__ == "__main__":
    start_pub_sub_consumer()
    listen_to_study_progress("http://localhost:5005/echo")
    listen_to_quiz_question("http://localhost:5005/echo")
    # This tests that we will send the same message to multiple endpoints
    listen_to_study_progress("http://localhost:5005/echo")

    time.sleep(2)
    event = StudyProgressEvent(username="Study Progress Alice", subject="math", topic="algebra",
                               update="completed quiz 1")
    update_study_progress(event)

    event = StudyProgressEvent(username="Study Progress Dave", subject="math", topic="algebra",
                               update="completed quiz 1")
    update_study_progress(event)

    event = QuizQuestionEvent(username="Quiz Dave", subject="math", topic="algebra", quiz_question="What is 2+2?")
    update_quiz_question(event)

    event = QuizQuestionEvent(username="Quiz Alice", subject="math", topic="algebra", quiz_question="What is 2+3?")
    update_quiz_question(event)

    time.sleep(10)
