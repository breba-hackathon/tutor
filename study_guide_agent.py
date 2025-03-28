from langchain_google_vertexai import ChatVertexAI


def get_study_guide():
    # Create the Gemini model
    model = ChatVertexAI(model_name="gemini-2.0-flash-001", location='us-west1')

    response = model.invoke("Create me a study guide for pythagorean theorem. About 1 page long")

    return response.content


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    print(get_study_guide())
