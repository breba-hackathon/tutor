import json
import threading
import asyncio
import time

import aiohttp
from typing import List
from kafka import KafkaConsumer, KafkaProducer
from pydantic import BaseModel

# Constants
KAFKA_BROKER = 'localhost:9092'
TOPIC = 'study_progress'

# Global subscriber list
_subscribers: List[str] = []

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

def listen_to_study_progress(endpoint: str) -> None:
    """
    Register an endpoint to receive updates from the 'study_progress' topic.
    """
    if endpoint not in _subscribers:
        _subscribers.append(endpoint)

    # Start the consumer in a background thread
    if not hasattr(listen_to_study_progress, '_consumer_thread'):
        t = threading.Thread(target=_start_async_consumer, daemon=True)
        t.start()
        listen_to_study_progress._consumer_thread = t

def update_study_progress(event: StudyProgressEvent) -> None:
    """
    Publish a new event to the 'study_progress' Kafka topic.
    """
    _producer.send(TOPIC, event.model_dump())
    _producer.flush()

def _start_async_consumer():
    asyncio.run(_consume_and_forward_async())

async def _consume_and_forward_async():
    loop = asyncio.get_event_loop()
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='study_progress_forwarder'
    )
    async with aiohttp.ClientSession() as session:
        for msg in consumer:
            event = msg.value
            tasks = [
                _post_event(session, endpoint, event)
                for endpoint in _subscribers
            ]
            await asyncio.gather(*tasks)

async def _post_event(session: aiohttp.ClientSession, endpoint: str, event: dict):
    try:
        async with session.post(endpoint, json=event, timeout=30) as resp:
            if resp.status != 200:
                print(f"Failed to post to {endpoint}, status code: {resp.status}")
    except Exception as e:
        print(f"Failed to post to {endpoint}: {e}")


if __name__ == "__main__":
    listen_to_study_progress("http://localhost:5005/progress")

    time.sleep(2)
    event = StudyProgressEvent(
        username="alice",
        subject="math",
        topic="algebra",
        update="completed quiz 1"
    )
    update_study_progress(event)

    time.sleep(10)