import json

from flask import Flask, render_template, request, session, jsonify, send_file
import io
import markdown

from agents.study_guide_agent import StudyGuideAgent, STUDY_GUIDE_BUILDER, QUIZ_QUESTION_BUILDER
from agents.study_progress import StudyProgressAgent
from model.tutor import sample_data
from services.agent_pub_sub import listen_to_study_progress, start_pub_sub_consumer

app = Flask(__name__)

# TODO: This could be a mapping of topicId to thread_id, this would offload concurrency issues to database that keeps agent state
agent: StudyGuideAgent | None = None
progress_agent: StudyProgressAgent | None = None

# Start the pub sub consumer so that agents can listen to and publish to events
start_pub_sub_consumer()


@app.route("/")
def tutor():
    return render_template("tutor.html", subjects=sample_data.subjects)


@app.route("/study_guide")
def study_guide():
    global agent
    global progress_agent
    subject = request.args.get("subject", "Unknown Subject")
    topic = request.args.get("topic", "Unknown Topic")
    username = request.args.get("username", "Anonymous")

    # TODO: username, subject, topic, should be passed in at invoke time, not at initialization
    agent = StudyGuideAgent(username=username, subject=subject, topic=topic)
    progress_agent = StudyProgressAgent(username=username)
    guide_markdown = agent.invoke(STUDY_GUIDE_BUILDER)
    guide_html = markdown.markdown(guide_markdown)
    return render_template("study_guide.html", topic=topic, study_guide=guide_html)


@app.route("/quiz")
def quiz():
    global agent
    if agent:
        quiz_question_raw = agent.invoke(QUIZ_QUESTION_BUILDER)
        quiz_question = json.loads(quiz_question_raw)
        quiz_questions = [quiz_question]
        return render_template("quiz.html", quiz_questions=quiz_questions)
    else:
        return "Error: No agent initialized. Go to /study_guide first.", 400


@app.route("/grade_quiz", methods=["POST"])
def grade_quiz():
    data = request.get_json()

    explanation = agent.grade_quiz_question(json.dumps({
        **data,
        "correct": data["selected"] == data["answer"],
    }))

    return jsonify({
        **data,
        "correct": data["selected"] == data["answer"], "explanation": explanation
    })


@app.route("/new_study_guide")
def new_study_guide():
    return render_template("new_study_guide.html")


@app.route('/audio')
def audio():
    return render_template('audio.html')


@app.route('/audio/lesson.mp3')
def serve_audio():
    with open("audio/lesson.mp3", "rb") as f:
        audio_data = f.read()
    return send_file(io.BytesIO(audio_data), mimetype="audio/mpeg")


@app.route('/agent/update_progress', methods=["POST"])
def update_progress():
    data = request.get_json()
    progress_agent.inject_graded_quiz_question(data["quiz_question"], data["subject"], data["topic"])

    return "OK", 200

@app.route("/echo", methods=["POST"])
def echo():
    text = request.get_data().decode("utf-8")
    return text, 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5005)
