from typing import Literal

from pydantic import BaseModel


# TODO: get study progress agent to use the same models
class Topic(BaseModel):
    name: str
    quiz_questions: list[str] = []
    level: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10] = 1
    summary: str = ""
    study_guide: str = ""
    audio_file_location: str = ""


class Subject(BaseModel):
    name: str
    topics: dict[str, Topic]


class TutorContent(BaseModel):
    subjects: dict[str, Subject]

    def find_or_create_topic(self, subject_name: str, topic_name: str):
        subject = self.subjects.get(subject_name)
        if subject is None:
            subject = Subject(name=subject_name, topics={})
            self.subjects[subject_name] = subject

        if subject.topics.get(topic_name) is None:
            topic = Topic(name=topic_name)
            subject.topics[topic_name] = topic

        return subject.topics.get(topic_name)


sample_data = TutorContent(subjects={
    "Pre-Algebra": Subject(
        name="Pre-Algebra",
        topics={
            "Integers": Topic(name="Integers", level=10),
            "Fractions": Topic(name="Fractions", level=3),
            "Decimals": Topic(name="Decimals", level=7),
        }
    ),
    "Algebra": Subject(
        name="Algebra",
        topics={
            "Linear Equations": Topic(name="Linear Equations", level=10),
            "Quadratic Equations": Topic(name="Quadratic Equations", level=5),
            "Exponents": Topic(name="Exponents", level=1),
        }
    ),
    "Geometry": Subject(
        name="Geometry",
        topics={
            "Pythagorean Theorem": Topic(name="Pythagorean Theorem", level=2),
            "Angles": Topic(name="Angles", level=1),
            "Circles": Topic(name="Circles", level=1),
        }
    ),
})
