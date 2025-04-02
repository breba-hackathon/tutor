from typing import Literal

from langchain_core.messages import AnyMessage
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from agents.instruction_reader import get_instructions


class StudyGuide(BaseModel):
    text: str
    audio_file_location: str


study_guide_builder_agent: CompiledGraph | None = None


@tool
def build_study_guide(subject, topic, progress_summary: str, style: Literal["textbook", "podcast"]):
    """
        Generate a study guide text.

        Args:
            subject (str): The subject name for the study guide.
            topic (str): the topic name for the study guide.
            progress_summary (str): A summary of the user's progress or current understanding. If you don't have one pass "No Information Yet"
            style (Literal["textbook", "podcast"]): The desired style for the study guide
        """
    system_prompt = get_instructions("study_guide_builder")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Progress summary: {progress_summary}"},
        {"role": "user",
         "content": f"Create a study guide for subject=`{subject}` and topic=`{topic}`. "
                    f"The study guide should be written in style of {style}."
                    f"It should be about half page long or 5 minutes long depending on style provide"},
    ]
    model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')
    response = model.invoke(messages)
    return response.content


@tool
def create_audio_file(text: str):
    """create audio file for podcast style study guide"""
    return "audio/lesson.mp3"


# TODO use tool to pull textbook out of database

def init_study_guide_builder_agent():
    global study_guide_builder_agent
    tools = [build_study_guide, create_audio_file]
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    study_guide_builder_agent = create_react_agent(
        llm, tools, response_format=StudyGuide,
        prompt="You are an agent trying to generate a study guide given user request. You will do exactly what your told. Don't make anything up.")


def invoke_study_guide_builder_agent(subject_name: str, topic_name: str, progress_summary: str,
                                     context: list[AnyMessage]) -> StudyGuide:
    messages = context + [
        {"role": "user", "content": f"Progress summary: {progress_summary}"},
        {"role": "user",
         "content": f"Generate a study guide for subject=`{subject_name}` and topic=`{topic_name}`. The study style will be textbook and the person will read it."},
    ]
    if study_guide_builder_agent is None:
        init_study_guide_builder_agent()

    stream = study_guide_builder_agent.stream({"messages": messages}, stream_mode="values")

    state_update = {}
    for state_update in stream:
        state_update["messages"][-1].pretty_print()

    return state_update.get("structured_response")


if __name__ == "main":
    from dotenv import load_dotenv

    load_dotenv()
    input_messages = {"messages": [
        {"role": "system",
         "content": get_instructions("study_guide_builder_react_prompt")},
        # {"role": "user",
        #  "content": "Generate a study guide for subject=`math` and topic=`algebra`. The study style will be textbook and it will be read by a person."}]}
        {"role": "user",
         "content": "Generate a study guide for subject=`math` and topic=`algebra`. The study style will be podcast and the person will listen to it."}]}
    event = study_guide_builder_agent.invoke(input_messages)

    structured_response = event.get("structured_response")
    print(structured_response)
