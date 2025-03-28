from pydantic import BaseModel
from typing import List


class Topic(BaseModel):
    name: str


class Subject(BaseModel):
    name: str
    topics: List[Topic]


class TutorContent(BaseModel):
    subjects: List[Subject]


sample_data = TutorContent(subjects=[
    Subject(name="Pre-Algebra", topics=[
        Topic(name="Integers"),
        Topic(name="Fractions"),
        Topic(name="Decimals"),
    ]),
    Subject(name="Algebra", topics=[
        Topic(name="Linear Equations"),
        Topic(name="Quadratic Equations"),
        Topic(name="Exponents"),
    ]),
    Subject(name="Geometry", topics=[
        Topic(name="Pythagorean Theorem"),
        Topic(name="Angles"),
        Topic(name="Circles"),
    ]),
])

