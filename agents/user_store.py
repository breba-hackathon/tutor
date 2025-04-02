import sqlite3
from collections import defaultdict

from model.tutor import TutorContent, Subject, Topic

user_mapping: dict[str, int] = {}


def add_user(user_id: str, thread_id: int):
    user_mapping[user_id] = thread_id


def get_next_thread_id() -> int:
    if len(user_mapping) == 0:
        return 1
    else:
        return max(user_mapping.values()) + 1


def get_thread_id(user_id: str):
    if user_id in user_mapping:
        return user_mapping[user_id]
    else:
        thread_id = get_next_thread_id()
        add_user(user_id, thread_id)
        return thread_id


def get_user_id(thread_id: int):
    for user_id, thread in user_mapping.items():
        if thread == thread_id:
            return user_id


def default_tutor_content() -> TutorContent:
    """
    Gets data for seeding agent state.
    :return: data for seeding agent state.
    """
    conn = sqlite3.connect("study_material.db")
    cursor = conn.cursor()

    # Dict to build: subject -> topic_name -> Topic instance
    subjects_dict: dict[str, Subject] = {}

    cursor.execute("SELECT subject, topic FROM topics")
    rows = cursor.fetchall()
    conn.close()

    # Organize into your structure
    subject_topic_map: dict[str, dict[str, Topic]] = defaultdict(dict)
    for subject, topic in rows:
        subject_topic_map[subject][topic] = Topic(name=topic)

    for subject_name, topic_dict in subject_topic_map.items():
        subjects_dict[subject_name] = Subject(
            name=subject_name,
            topics=topic_dict
        )

    return TutorContent(subjects=subjects_dict)
