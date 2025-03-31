from typing import Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph, MessagesState
from pydantic import BaseModel

from agents.instruction_reader import get_instructions


class NextLevel(BaseModel):
    next_level: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class Topic(BaseModel):
    name: str
    quiz_questions: list[str]
    level: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class Subject(BaseModel):
    name: str
    topics: dict[str, Topic]


class State(MessagesState):
    subjects: dict[str, Subject]
    graded_quiz_question: str
    subject: str
    topic: str


user_mapping: dict[str, int] = {}


def get_next_thread_id():
    if len(user_mapping) == 0:
        return 1
    else:
        return max(user_mapping.values()) + 1


class StudyProgressAgent:
    def __init__(self, username: str, subject: str, topic: str):
        self.username = username
        self.subject = subject
        self.topic = topic

        self.supervisor_prompt = get_instructions("study_progress")

        thread_id = user_mapping.get(self.username, get_next_thread_id())
        # Setup persistence
        self.config = {"configurable": {"thread_id": thread_id}}
        checkpointer = MemorySaver()

        self.model = ChatOpenAI(model="gpt-4o")
        # self.model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')
        builder = StateGraph(State)
        builder.add_node("entry_node", self.entry_node)
        builder.add_edge(START, "entry_node")
        builder.add_edge("entry_node", END)

        self.graph = builder.compile(checkpointer=checkpointer)

    def entry_node(self, state: State):
        subject = state["subject"]
        topic = state["topic"]
        graded_quiz_question = state["graded_quiz_question"]
        current_topic = Topic(name=topic, level=1, quiz_questions=[])
        current_subject = Subject( name=subject, topics={topic: current_topic} )

        subjects = state.get("subjects", {})
        subject_obj = subjects.get(subject, current_subject)

        topic_obj = subject_obj.topics.setdefault(topic, current_topic)
        topic_obj.quiz_questions += [graded_quiz_question]

        subjects[subject] = subject_obj
        return { "subjects": subjects }

    def inject_graded_quiz_question(self, graded_quiz_question: str, subject: str, topic: str):
        final_state = self.graph.invoke({
            "subject": subject,
            "topic": topic,
            "graded_quiz_question": graded_quiz_question
        }, self.config)

        return final_state


if __name__ == "__main__":
    load_dotenv()
    agent = StudyProgressAgent(username="John Doe", subject="Pre-Algebra", topic="Integers")
    agent.inject_graded_quiz_question("Question 1", "Pre-Algebra", "Integers")
    agent.inject_graded_quiz_question("Question 2", "Pre-Algebra", "Integers")
    agent.inject_graded_quiz_question("Decimals Question 1", "Pre-Algebra", "Decimals")
    response = agent.inject_graded_quiz_question("Equations Question 1", "Algebra", "Equations")
    assert response["subjects"].get("Pre-Algebra").topics.get("Integers").quiz_questions == ["Question 1", "Question 2"]
    assert response["subjects"].get("Pre-Algebra").topics.get("Integers").level == 1
    assert response["subjects"].get("Pre-Algebra").topics.get("Integers").name == "Integers"


    assert response["subjects"].get("Pre-Algebra").topics.get("Decimals").quiz_questions == ["Decimals Question 1"]
    assert response["subjects"].get("Pre-Algebra").topics.get("Decimals").level == 1
    assert response["subjects"].get("Pre-Algebra").topics.get("Decimals").name == "Decimals"

    assert response["subjects"].get("Algebra").topics.get("Equations").quiz_questions == ["Equations Question 1"]
    assert response["subjects"].get("Algebra").topics.get("Equations").level == 1
    assert response["subjects"].get("Algebra").topics.get("Equations").name == "Equations"