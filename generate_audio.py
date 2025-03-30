from pathlib import Path
from openai import OpenAI

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

client = OpenAI()
speech_file_path = Path(__file__).parent / "audio/lesson.mp3"

with client.audio.speech.with_streaming_response.create(
    model="gpt-4o-mini-tts",
    voice="fable",
    input="Today is a wonderful day to build something people love!",
    instructions="Speak gently, with a soothing and calm tone to create a relaxed atmosphere."
,
) as response:
    response.stream_to_file(speech_file_path)


