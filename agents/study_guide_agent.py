from langchain_google_vertexai import ChatVertexAI

def generate_study_guide(topic: str) -> str:

    # Create the Gemini model
    model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')

    response = model.invoke(f"Create me a study guide for {topic}. About 1 page long")

    return response.content


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    print(generate_study_guide("algebra"))
