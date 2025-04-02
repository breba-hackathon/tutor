import sqlite3
from pathlib import Path
from typing import Literal

from langchain_core.messages import AnyMessage
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import create_react_agent
from openai import OpenAI
from pydantic import BaseModel, Field

from agents.instruction_reader import get_instructions


class StudyGuide(BaseModel):
    study_guide_text: str = Field(..., description="The study guide text in plain or markdown format.")
    audio_file_location: str
    agent_comment: str = Field(..., description="A comment from the agent.")


study_guide_builder_agent: CompiledGraph | None = None
db_schema = None

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
                    f"It should be about half page long or 3 minutes long depending on style provide"},
    ]
    model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')
    response = model.invoke(messages)
    return response.content


@tool
def create_audio_file(username:str, subject_name: str, topic_name: str, text: str):
    """create audio file for podcast style study guide"""
    client = OpenAI()

    with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="fable",
            input=text,
            instructions="Speak gently, with a soothing and calm tone to create a relaxed atmosphere."
            ,
    ) as response:
        # TODO: pass in a callback for writing to a file
        speech_file_path =  f"audio/{username}_{subject_name}_{topic_name}.mp3"
        print(f"Writing audio to {speech_file_path}")
        response.stream_to_file(Path.cwd() / speech_file_path)
    return speech_file_path


@tool
def query_database(query: str):
    """
    Use this tool to query the database.
    Query DB schema first to learn about database structure.
    """
    # Basic check to ensure only SELECT statements are allowed
    if not query.strip().lower().startswith("select") and not query.strip().lower().startswith("pragma"):
        raise ValueError("Only SELECT queries are allowed.")

    conn = sqlite3.connect("study_material.db")
    cursor = conn.cursor()

    try:
        cursor.execute(query)
        result = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        result = []
    finally:
        conn.close()

    return result


def init_study_guide_builder_agent():
    global study_guide_builder_agent, db_schema
    db_schema = query_database("SELECT sql FROM sqlite_master WHERE type='table'")
    tools = [build_study_guide, create_audio_file, query_database]
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    prompt = get_instructions("study_guide_builder_react_prompt")
    study_guide_builder_agent = create_react_agent(
        llm, tools, response_format=StudyGuide,
        prompt=prompt)


def invoke_study_guide_builder_agent(username: str, subject_name: str, topic_name: str, progress_summary: str,
                                     context: list[AnyMessage],
                                     study_guide_style: Literal["textbook", "podcast"]) -> StudyGuide:
    if study_guide_builder_agent is None:
        init_study_guide_builder_agent()

    prompt = get_instructions("study_guide_builder_react_prompt", db_schema=db_schema)
    messages = [{"role": "system", "content": prompt}] + context + [
        {"role": "user", "content": f"Progress summary: {progress_summary}"},
        {"role": "user",
         "content": f"For user=`{username}`, Get book contents from the database and then Generate a study guide for subject=`{subject_name}` and topic=`{topic_name}`. The study style will be {study_guide_style} and the person will read it."},
    ]

    stream = study_guide_builder_agent.stream({"messages": messages}, stream_mode="values")

    state_update = {}
    for state_update in stream:
        state_update["messages"][-1].pretty_print()

    return state_update.get("structured_response")

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    result = invoke_study_guide_builder_agent("Yason", "Data Structures", "Heap", "", [], "textbook")

    print(result)
