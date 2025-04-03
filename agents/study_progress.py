from typing import Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph, MessagesState
from pydantic import BaseModel

from agents.instruction_reader import get_instructions
from agents.user_store import get_thread_id
from model.tutor import Subject, Topic
from services.agent_pub_sub import update_study_progress, StudyProgressEvent, listen_to_quiz_question


class Progress(BaseModel):
    next_level: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    progress_summary: str


class State(MessagesState):
    username: str
    subjects: dict[str, Subject]
    graded_quiz_question: str
    subject: str
    topic: str


listen_to_quiz_question("http://localhost:5005/agent/update_progress")


class StudyProgressAgent:
    def __init__(self, ):
        # Setup persistence
        checkpointer = MemorySaver()

        self.model = ChatOpenAI(model="gpt-4o")
        # self.model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')
        builder = StateGraph(State)
        builder.add_node("entry_node", self.entry_node)
        builder.add_node("progress_update", self.progress_update)
        builder.add_node("publish_update", self.publish_update)
        builder.add_edge(START, "entry_node")
        builder.add_edge("entry_node", "progress_update")
        builder.add_edge("progress_update", "publish_update")
        builder.add_edge("publish_update", END)

        self.graph = builder.compile(checkpointer=checkpointer)

    def entry_node(self, state: State):
        """
        This node sets up the state for the study progress agent by adding quiz question to the state.
        If subject and topic don't it exist, it will create them.
        """
        subject = state["subject"]
        topic = state["topic"]
        graded_quiz_question = state["graded_quiz_question"]

        current_topic = Topic(name=topic, level=1, quiz_questions=[], summary="")
        current_subject = Subject(name=subject, topics={topic: current_topic})

        subjects = state.get("subjects", {})
        subject_obj = subjects.get(subject, current_subject)

        topic_obj = subject_obj.topics.setdefault(topic, current_topic)
        topic_obj.quiz_questions += [graded_quiz_question]

        subjects[subject] = subject_obj
        return {"subjects": subjects}

    def progress_update(self, state: State):
        """
        This node actually performs the study progress update
        :param state:
        :return:
        """
        subjects = state["subjects"]
        current_topic = subjects.get(state["subject"]).topics.get(state["topic"])
        prompt = get_instructions("progress_update",
                                  subject=state["subject"],
                                  topic=state["topic"],
                                  quiz_questions=current_topic.quiz_questions,
                                  level=current_topic.level)
        messages = [{"role": "system", "content": prompt},
                    {"role": "user",
                     "content": f"Provide learning summary and next level given my last quiz questions and answers"}]
        response = self.model.with_structured_output(Progress).invoke(messages)
        current_topic.level = response.next_level
        current_topic.summary = response.progress_summary

        return {"subjects": subjects}

    def publish_update(self, state: State):
        """
        This node publishes the study progress update so that other agents can consume it
        """
        subjects = state["subjects"]
        topic = subjects.get(state["subject"]).topics.get(state["topic"])
        update_study_progress(
            StudyProgressEvent(username=state["username"], subject=state["subject"], topic=state["topic"],
                               update=topic.summary, level=topic.level))

        return state

    def inject_graded_quiz_question(self, username: str, graded_quiz_question: str, subject: str, topic: str):
        """
        This node injects the graded quiz question into the state. The quiz questions are coming from quiz grader
        Args:
            username: username used to load agent state
            graded_quiz_question: the graded quiz question that will be injected into this agent's state
            subject: subject for the graded quiz question
            topic: topic for the graded quiz question
        """
        config = {"configurable": {"thread_id": get_thread_id(username)}}
        final_state = self.graph.invoke({
            "username": username,
            "subject": subject,
            "topic": topic,
            "graded_quiz_question": graded_quiz_question
        }, config)

        return final_state


if __name__ == "__main__":
    load_dotenv()
    agent = StudyProgressAgent()

    # Test entry node
    response = agent.entry_node(
        {"username": "John Doe", "messages": [], "subjects": {}, "graded_quiz_question": "Question 1",
         "subject": "Pre-Algebra", "topic": "Integers"})
    response = agent.entry_node(
        {"username": "John Doe", "messages": [], "subjects": response["subjects"], "graded_quiz_question": "Question 2",
         "subject": "Pre-Algebra", "topic": "Integers"})
    response = agent.entry_node({"username": "John Doe", "messages": [], "subjects": response["subjects"],
                                 "graded_quiz_question": "Decimals Question 1", "subject": "Pre-Algebra",
                                 "topic": "Decimals"})
    response = agent.entry_node({"username": "John Doe", "messages": [], "subjects": response["subjects"],
                                 "graded_quiz_question": "Equations Question 1", "subject": "Algebra",
                                 "topic": "Equations"})
    assert response["subjects"].get("Pre-Algebra").topics.get("Integers").quiz_questions == ["Question 1", "Question 2"]
    assert response["subjects"].get("Pre-Algebra").topics.get("Integers").level == 1
    assert response["subjects"].get("Pre-Algebra").topics.get("Integers").name == "Integers"

    assert response["subjects"].get("Pre-Algebra").topics.get("Decimals").quiz_questions == ["Decimals Question 1"]
    assert response["subjects"].get("Pre-Algebra").topics.get("Decimals").level == 1
    assert response["subjects"].get("Pre-Algebra").topics.get("Decimals").name == "Decimals"

    assert response["subjects"].get("Algebra").topics.get("Equations").quiz_questions == ["Equations Question 1"]
    assert response["subjects"].get("Algebra").topics.get("Equations").level == 1
    assert response["subjects"].get("Algebra").topics.get("Equations").name == "Equations"

    # Test instructions
    instructions = get_instructions(
        "progress_update",
        subject="Mathematics",
        topic="Fractions",
        quiz_questions=[
            "What is 1/2 + 1/3?",
            "Simplify 3/6",
        ],
        level=3)

    assert "What is 1/2 + 1/3?" in instructions
    assert "Simplify 3/6" in instructions

    # Test progress update
    agent.inject_graded_quiz_question("John Doe", "{question: 2+2, answer: 3, correct: false}", "Pre-Algebra",
                                      "Integers")
    agent.inject_graded_quiz_question("John Doe", "{question: 5*4, answer: 20, correct: true}", "Pre-Algebra",
                                      "Integers")
    response = agent.inject_graded_quiz_question("John Doe", "{question: 0.4+0.3, answer: 0.7, correct: true}",
                                                 "Pre-Algebra",
                                                 "Decimals")
    assert response["subjects"].get("Pre-Algebra").topics.get("Integers").summary is not None
    assert response["subjects"].get("Pre-Algebra").topics.get("Decimals").summary is not None
    print(response)
