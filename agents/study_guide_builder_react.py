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
def create_audio_file(username:str, subject_name: str, topic_name: str, text: str):
    """create audio file for podcast style study guide"""
    client = OpenAI()

    with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="fable",
            input=text,
            instructions="Speak in an engaging way but also stay calm to give the listener confidence."
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
    tools = [create_audio_file, query_database]
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
