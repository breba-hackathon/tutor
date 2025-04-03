from typing import Literal, TypedDict, NotRequired, TypeAlias

from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph, MessagesState
from langgraph.types import Command
from pydantic import BaseModel, Field

from agents.instruction_reader import get_instructions
from agents.study_guide_builder_react import invoke_study_guide_builder_agent
from agents.user_store import get_thread_id, default_tutor_content
from model.tutor import TutorContent
from services.agent_pub_sub import update_quiz_question, QuizQuestionEvent, listen_to_study_progress, StudyProgressEvent

# This will listen to study_progress topic and call the endpoint specified
listen_to_study_progress("http://localhost:5005/agent/update_study_guides")

STUDY_GUIDE_BUILDER = "study_guide_builder"
EXISTING_STUDY_GUIDE = "existing_study_guide"
QUIZ_QUESTION_BUILDER = "quiz_question_builder"
QUIZ_GRADER = "quiz_grader"
GENERAL_CHAT_AGENT = "general_chat_agent"
members = [STUDY_GUIDE_BUILDER, QUIZ_QUESTION_BUILDER, QUIZ_GRADER, EXISTING_STUDY_GUIDE, GENERAL_CHAT_AGENT]

options = members + ["FINISH"]


class QuizQuestion(BaseModel):
    question: str = Field(description="The question itself")
    # options: list[str] = Field(description="List of exactly 4 options", min_items=4, max_items=4)
    options: list[str] = Field(description="List of exactly 4 options")
    answer: Literal["A", "B", "C", "D"] = Field(description="The correct answer letter")
    level: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class Route(TypedDict):
    reason: str
    next: Literal[*options]


StudyGuidStyleType: TypeAlias = Literal["podcast", "textbook"]
LevelType: TypeAlias = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class State(MessagesState):
    username: str
    tutor_content: NotRequired[TutorContent]
    study_guide: NotRequired[str]
    study_guide_style: NotRequired[StudyGuidStyleType]
    audio_file_location: NotRequired[str]
    quiz_question: NotRequired[QuizQuestion]
    question_to_grade: NotRequired[str]
    explanation: NotRequired[str]
    subject: NotRequired[str]
    topic: NotRequired[str]
    level: NotRequired[LevelType]
    progress_summary: NotRequired[str]


class StudyGuideSupervisorAgent:
    def __init__(self):
        self.supervisor_prompt = get_instructions("study_guide_supervisor", members=members)

        # Setup persistence
        checkpointer = MemorySaver()

        self.model = ChatOpenAI(model="gpt-4o")
        # self.model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')
        builder = StateGraph(State)
        builder.add_node("init_data", self.init_data)
        builder.add_node("supervisor", self.supervisor_node)
        builder.add_node(self.study_guide_builder)
        builder.add_node(self.existing_study_guide)
        builder.add_node(self.quiz_question_builder)
        builder.add_node(self.quiz_grader)
        builder.add_node(self.general_chat_agent)
        builder.add_node(self.publish_quiz_question)
        builder.add_edge(START, "init_data")
        builder.add_edge("init_data", "supervisor")
        builder.add_edge("quiz_grader", "publish_quiz_question")
        builder.add_conditional_edges("existing_study_guide", self.has_study_guide,
                                      {True: END, False: "study_guide_builder"})
        # The llm does not understand instructions pertaining to lifecycle, so kind of have to END for now
        builder.add_edge("supervisor", END)

        self.graph = builder.compile(checkpointer=checkpointer)

    def init_data(self, state: State):
        if state.get("tutor_content"):
            return state
        else:
            return {"tutor_content": default_tutor_content()}

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

    def has_study_guide(self, state: State) -> bool:
        return state.get("study_guide") is not None

    def existing_study_guide(self, state: State):
        """
        This node is used to check if the study guide already exists for the topic and subject.
        It will set the state["study_guide"] if one exists.
        Otherwise, it will clear state["study_guide"].
        """
        tutor_content = state.get("tutor_content")
        topic = tutor_content.find_or_create_topic(state["subject"], state["topic"])
        if topic.study_guide:
            return {
                "tutor_content": tutor_content,
                "study_guide": topic.study_guide,
                "level": topic.level,
                "progress_summary": topic.summary,
                "messages": [
                    HumanMessage(
                        content=f"Below is the study guide for subject: {state['subject']}, topic: {state['topic']}",
                        name="study_guide_builder"),
                    HumanMessage(content=topic.study_guide, name="study_guide_builder")
                ]
            }
        else:

            return {
                "messages": ["No study guide found for subject: " + state["subject"] + ", topic: " + state["topic"]],
                "tutor_content": tutor_content, "study_guide": None,
            }

    def study_guide_builder(self, state: State) -> Command[Literal["supervisor", END]]:
        """Generate a study guide for a given subject and topic."""
        response = invoke_study_guide_builder_agent(
            state["username"],
            state["subject"],
            state["topic"],
            state.get("progress_summary"),
            state["messages"],
            state.get("study_guide_style", "textbook")
        )

        tutor_content = state.get("tutor_content", TutorContent(subjects={}))
        topic = tutor_content.find_or_create_topic(state["subject"], state["topic"])
        topic.study_guide = response.study_guide_text
        topic.audio_file_location = response.audio_file_location
        # Update level when building study guide after progress update
        if state.get("level"):
            topic.level = state["level"]

        return Command(
            update={
                "tutor_content": state["tutor_content"],
                "study_guide": topic.study_guide,
                "audio_file_location": topic.audio_file_location,
                "level": topic.level,
                "messages": [
                    HumanMessage(content="The following message is from study_guide_builder",
                                 name="study_guide_builder"),
                    HumanMessage(content=topic.study_guide, name="study_guide_builder")
                ]
            },
            goto=END
        )

    def quiz_question_builder(self, state: State) -> Command[Literal["supervisor"]]:
        """Generate a quiz question when requested"""

        system_prompt = "You are providing a multiple choice question for a study guide mentioned earlier. You will provide 4 options and the correct answer. But do not repeat questions. Every time come up with a new question. For math questions use numbers and symbols more than words, but throw in a word problem sometimes."
        messages = [
                       {"role": "system", "content": system_prompt},
                   ] + state["messages"]
        messages.append({"role": "user", "content": f"Given the study guide: {state['study_guide']}"})
        messages.append({"role": "user",
                         "content": f"Create a quiz question for the study guide. Make the difficulty level {state.get('level')} out of 10"})
        model = ChatOpenAI(model="gpt-4o")
        model = model.with_structured_output(QuizQuestion)

        question = model.invoke(messages)

        return Command(
            update={
                "quiz_question": question,
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
        model = ChatOpenAI(model="gpt-4o", temperature=0)

        explanation_response = model.invoke(messages)

        return {
            "explanation": explanation_response.content,
            "messages": [
                HumanMessage(content="The following message is from quiz_grader",
                             name="quiz_grader"),
                HumanMessage(content=explanation_response.content, name="quiz_grader")
            ]
        }

    def general_chat_agent(self, state: State) -> Command[Literal["supervisor"]]:
        """Can respond to miscellaneous questions and other inquires"""
        system_prompt = "You are a helpful assistant. You are providing responses to user inquires based on the study guide and other information that you have."
        messages = [
                       {"role": "system", "content": system_prompt},
                   ] + state["messages"]

        model = ChatOpenAI(model="gpt-4o", temperature=0.2)

        chat_response = model.invoke(messages)

        update_messages = {"messages": [
            HumanMessage(content="The following message is from general_chat_agent",
                         name="general_chat_agent"),
            HumanMessage(content=chat_response.content, name="general_chat_agent")
        ]
        }

        return Command(update=update_messages, goto=END)

    def publish_quiz_question(self, state: State) -> Command[Literal["supervisor"]]:
        """
        Publishes the quiz question/answer and explanation to other agents
        The payload is plain text because agent to agent communication is greate with unstructured data.
        """
        payload = state["question_to_grade"] + "\n" + state["explanation"]
        update_quiz_question(
            QuizQuestionEvent(username=state["username"], subject=state["subject"], topic=state["topic"],
                              quiz_question=payload))

        return Command(goto=END)

    def find_existing_study_guide_or_create(self, username: str, subject: str, topic: str,
                                            style: StudyGuidStyleType) -> State:
        config = {"configurable": {"thread_id": get_thread_id(username)}}
        final_state = self.graph.invoke({
            "username": username, "subject": subject, "topic": topic, "study_guide_style": style,
            "messages": [{"role": "user", "content": EXISTING_STUDY_GUIDE}]
        }, config)
        # TODO: if style == "podcast" and no audio file, ask to create one again

        return final_state

    def build_quiz_question(self, username: str) -> QuizQuestion:
        config = {"configurable": {"thread_id": get_thread_id(username)}}
        final_state = self.graph.invoke({
            "messages": [{"role": "user", "content": QUIZ_QUESTION_BUILDER}]
        }, config)
        return final_state["quiz_question"]

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

    def update_study_guides(self, event: StudyProgressEvent) -> str:
        config = {"configurable": {"thread_id": get_thread_id(event.username)}}
        final_state = self.graph.invoke({
            "username": event.username, "subject": event.subject, "topic": event.topic, "level": event.level,
            "progress_summary": event.update,
            "messages": [{"role": "user",
                          "content": f"When building a study guide for subject: {event.subject}, topic: {event.topic}, take into account this progress update: {event.update}"},
                         {"role": "user", "content": STUDY_GUIDE_BUILDER}]
        }, config)
        return final_state["study_guide"]

    def get_tutor_content(self, username: str) -> TutorContent:
        config = {"configurable": {"thread_id": get_thread_id(username)}}
        content = self.graph.get_state(config).values.get("tutor_content")
        return content


if __name__ == "__main__":
    from dotenv import load_dotenv
    import time

    load_dotenv()

    # start_pub_sub_consumer()
    # listen_to_quiz_question("http://localhost:5005/echo")

    agent = StudyGuideSupervisorAgent()
    response = agent.grade_quiz_question("John Doe", "What is 2+2? The answer is: 3. This is not correct.")
    print(response)

    # Wait for the publish event to follow through
    time.sleep(5)
    # response = agent.invoke("Generate a study guide")
    # print(response)

    # response = agent.invoke("Create 2 quiz questions")
    # print(response)
