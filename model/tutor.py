from pydantic import BaseModel
from typing import List


class Topic(BaseModel):
    name: str
    proficiency: int


class Subject(BaseModel):
    name: str
    topics: List[Topic]


class TutorContent(BaseModel):
    subjects: List[Subject]


sample_data = TutorContent(subjects=[
    Subject(name="Pre-Algebra", topics=[
        Topic(name="Integers", proficiency=100),
        Topic(name="Fractions", proficiency=25),
        Topic(name="Decimals", proficiency=67),
    ]),
    Subject(name="Algebra", topics=[
        Topic(name="Linear Equations", proficiency=99),
        Topic(name="Quadratic Equations", proficiency=43),
        Topic(name="Exponents", proficiency=3),
    ]),
    Subject(name="Geometry", topics=[
        Topic(name="Pythagorean Theorem", proficiency=12),
        Topic(name="Angles", proficiency=0),
        Topic(name="Circles", proficiency=6),
    ]),
])

