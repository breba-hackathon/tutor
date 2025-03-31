import time
from typing import Literal, TypedDict, NotRequired

from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph, MessagesState
from langgraph.types import Command
from pydantic import BaseModel, Field

from agents.instruction_reader import get_instructions
from agents.user_store import get_thread_id
from services.agent_pub_sub import update_quiz_question, QuizQuestionEvent, start_pub_sub_consumer, listen_to_quiz_question

class QuizQuestion(BaseModel):
    question: str = Field(description="The question itself")
    options: list[str] = Field(description="List of options", min_items=4, max_items=4)
    answer: Literal["A", "B", "C", "D"] = Field(description="The correct answer letter")


class State(MessagesState):
    study_guide: NotRequired[str]
    question_to_grade: str
    explanation: str
    username: str
    subject: str
    topic: str


STUDY_GUIDE_BUILDER = "study_guide_builder"
QUIZ_QUESTION_BUILDER = "quiz_question_builder"
QUIZ_GRADER = "quiz_grader"
members = [STUDY_GUIDE_BUILDER, QUIZ_QUESTION_BUILDER, QUIZ_GRADER]

options = members + ["FINISH"]


class Route(TypedDict):
    reason: str
    next: Literal[*options]


class StudyGuideAgent:
    def __init__(self, username: str, subject: str, topic: str):
        self.supervisor_prompt = get_instructions("study_guide", members=members)

        # Setup persistence
        checkpointer = MemorySaver()

        self.model = ChatOpenAI(model="gpt-4o")
        # self.model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')
        builder = StateGraph(State)
        builder.add_node("supervisor", self.supervisor_node)
        builder.add_node(self.study_guide_builder)
        builder.add_node(self.quiz_question_builder)
        builder.add_node(self.quiz_grader)
        builder.add_node(self.publish_quiz_question)
        builder.add_edge(START, "supervisor")
        builder.add_edge("quiz_grader", "publish_quiz_question")
        # The llm does not understand instructions pertaining to lifecycle, so kind of have to END for now
        builder.add_edge("supervisor", END)

        self.graph = builder.compile(checkpointer=checkpointer)

    def supervisor_node(self, state: State) -> Command[Literal[*members, "__end__"]]:
        # This allows using deterministic routing, but keeping
        if state["messages"][-1].content in members:
            goto = state["messages"][-1].content
        else:
            messages = [
                           {"role": "system", "content": self.supervisor_prompt},
                       ] + state["messages"]
            response = self.model.with_structured_output(Route).invoke(messages)
            goto = response["next"]

        if goto == "FINISH":
            goto = END

        return Command(goto=goto, update={"next": goto})

    def study_guide_builder(self, state: State) -> Command[Literal["supervisor"]]:
        """Generate a study guide for a given topic. """

        system_prompt = get_instructions("study_guide_builder")
        messages = [
                       {"role": "system", "content": system_prompt},
                   ] + state["messages"]
        messages.append({"role": "user", "content": f"Create a study guide for subject=`{state["subject"]}` and topic=`{state["topic"]}`. About half page long."})

        model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')

        response = model.invoke(messages)

        return Command(
            update={
                "study_guide": response.content,
                "messages": [
                    HumanMessage(content="The following message is from study_guide_builder",
                                 name="study_guide_builder"),
                    HumanMessage(content=response.content, name="study_guide_builder")
                ]
            },
            goto=END
        )

    def quiz_question_builder(self, state: State) -> Command[Literal["supervisor"]]:
        """Generate a quiz question when requested"""

        system_prompt = "You are providing a multiple choice question for a study guide mentioned earlier. You will provide 4 options and the correct answer."
        messages = [
                       {"role": "system", "content": system_prompt},
                   ] + state["messages"]
        messages.append({"role": "user", "content": "Create a quiz question for the study guide"})
        model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')
        model = model.with_structured_output(QuizQuestion)

        question = model.invoke(messages)

        return Command(
            update={
                "messages": [
                    HumanMessage(content="The following message is from quiz_question_builder",
                                 name="quiz_question_builder"),
                    HumanMessage(content=question.model_dump_json(), name="quiz_question_builder")
                ]
            },
            goto=END
        )

    def quiz_grader(self, state: State):
        """Generates an explanation for your question/answer"""
        system_prompt = "You are providing an explanation for answers to quiz questions, and why the selected answer was correct/incorrect. Do not use markdown and output in plain text without any formatting. IMPORTANT! You are not in a chat with a person."
        messages = [
                       {"role": "system", "content": system_prompt},
                   ] + state["messages"]
        messages.append(
            {"role": "user", "content": "Provide an explanation for this question: " + state["question_to_grade"]})
        model = ChatVertexAI(model_name="gemini-1.5-pro", location='us-west1')

        explanation_response = model.invoke(messages)

        return {
            "explanation": explanation_response.content,
            "messages": [
                HumanMessage(content="The following message is from quiz_grader",
                             name="quiz_grader"),
                HumanMessage(content=explanation_response.content, name="quiz_grader")
            ]
        }

    def publish_quiz_question(self, state: State) -> Command[Literal["supervisor"]]:
        """
        Publishes the quiz question/answer and explanation to other agents
        The payload is plain text because agent to agent communication is greate with unstructured data.
        """
        payload = state["question_to_grade"] + "\n" + state["explanation"]
        update_quiz_question(
            QuizQuestionEvent(username=state["username"], subject=state["subject"], topic=state["topic"], quiz_question=payload))

        return Command(goto=END)

    def build_study_guide(self, username: str, subject: str, topic: str):
        config = {"configurable": {"thread_id": get_thread_id(username)}}
        final_state = self.graph.invoke({
            "username": username, "subject": subject, "topic": topic,
            "messages": [{"role": "user", "content": STUDY_GUIDE_BUILDER}]
        }, config)
        return final_state["study_guide"]

    def build_quiz_question(self, username: str):
        config = {"configurable": {"thread_id": get_thread_id(username)}}
        final_state = self.graph.invoke({
            "messages": [{"role": "user", "content": QUIZ_QUESTION_BUILDER}]
        }, config)
        return final_state["messages"][-1].content


    def invoke(self, username: str, user_input: str):
        config = {"configurable": {"thread_id": get_thread_id(username)}}
        final_state = self.graph.invoke({
            "messages": [{"role": "user", "content": user_input}]
        }, config)
        return final_state["messages"][-1].content

    def grade_quiz_question(self, username, quiz_question: str):
        """
        Runs the quiz grader graph.
        We will use deterministic routing for this case as well.
        We will use string data because this is agent ot agent communication and agents don't care about structure
        """
        config = {"configurable": {"thread_id": get_thread_id(username)}}
        final_state = self.graph.invoke({
            "question_to_grade": quiz_question,
            "messages": [{"role": "user", "content": QUIZ_GRADER}]
        }, config)
        return final_state["messages"][-1].content


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    start_pub_sub_consumer()
    listen_to_quiz_question("http://localhost:5005/echo")

    agent = StudyGuideAgent(username="John Doe", subject="Pre-Algebra", topic="Integers")
    response = agent.grade_quiz_question("What is 2+2? The answer is: 3. This is not correct.")
    print(response)

    # Wait for the publish event to follow through
    time.sleep(5)
    # response = agent.invoke("Generate a study guide")
    # print(response)

    # response = agent.invoke("Create 2 quiz questions")
    # print(response)
