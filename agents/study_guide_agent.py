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


class QuizQuestion(BaseModel):
    question: str = Field(description="The question itself")
    options: list[str] = Field(description="List of options", min_items=4, max_items=4)
    answer: Literal["A", "B", "C", "D"] = Field(description="The correct answer letter")


class State(MessagesState):
    study_guide: NotRequired[str]
    quiz: NotRequired[list[QuizQuestion]]


STUDY_GUIDE_BUILDER = "study_guide_builder"
QUIZ_QUESTION_BUILDER = "quiz_question_builder"
members = [STUDY_GUIDE_BUILDER, QUIZ_QUESTION_BUILDER]

options = members + ["FINISH"]


class Route(TypedDict):
    reason: str
    next: Literal[*options]


class StudyGuideAgent:
    def __init__(self, username: str, subject: str, topic: str):
        self.username = username
        self.subject = subject
        self.topic = topic

        self.supervisor_prompt = get_instructions("study_guide", members=members)

        # Setup persistence
        self.config = {"configurable": {"thread_id": "1"}}
        checkpointer = MemorySaver()

        self.model = ChatOpenAI(model="gpt-4o")
        # self.model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')
        builder = StateGraph(State)
        builder.add_node("supervisor", self.supervisor_node)
        builder.add_node(self.study_guide_builder)
        builder.add_node(self.quiz_question_builder)
        builder.add_edge(START, "supervisor")
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
        messages.append({"role": "user", "content": f"Create a study guide for {self.topic}. About half page long."})

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
            goto="supervisor"
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
            goto="supervisor"
        )

    def invoke(self, user_input: str):
        final_state = self.graph.invoke({
            "messages": [{"role": "user", "content": user_input}]
        }, self.config)
        return final_state["messages"][-1].content


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    agent = StudyGuideAgent(username="John Doe", subject="Pre-Algebra", topic="Integers")
    response = agent.invoke("Generate a study guide")
    print(response)

    response = agent.invoke("Create 2 quiz questions")
    print(response)
