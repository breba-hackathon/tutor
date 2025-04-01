import io
import json

import markdown
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, jsonify, send_file

from agents.study_guide_agent import StudyGuideAgent
from agents.study_progress import StudyProgressAgent
from model.tutor import sample_data
from services.agent_pub_sub import start_pub_sub_consumer

load_dotenv()
app = Flask(__name__)
# TODO: use secret storage for this
app.secret_key = 'your-secret-key-123'

study_guide_agent_instance: StudyGuideAgent = StudyGuideAgent()
progress_agent: StudyProgressAgent | None = None

# Start the pub sub consumer so that agents can listen to and publish to events
start_pub_sub_consumer()


@app.route("/")
def tutor():
    return render_template("tutor.html", subjects=sample_data.subjects)


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()  # Expecting JSON from JS fetch

    username = data.get('username')
    teaching_style = data.get('teachingStyle')

    # Save to session
    session['username'] = username
    session['teaching_style'] = teaching_style

    return jsonify({'message': f"Preferences saved for {username}"})


@app.route("/study_guide")
def study_guide():
    global progress_agent
    subject = request.args.get("subject", "Unknown Subject")
    topic = request.args.get("topic", "Unknown Topic")
    username = session.get('username', "Anonymous")
    progress_agent = StudyProgressAgent(username=username)
    guide_markdown = study_guide_agent_instance.find_existing_study_guide_or_create(username, subject, topic)
    guide_html = markdown.markdown(guide_markdown)
    return render_template("study_guide.html", subject=subject, topic=topic, study_guide=guide_html)


@app.route("/quiz")
def quiz():
    subject = request.args.get("subject", "Unknown Subject")
    topic = request.args.get("topic", "Unknown Topic")

    if study_guide_agent_instance:
        quiz_question_raw = study_guide_agent_instance.build_quiz_question(session.get('username', "Anonymous"))
        quiz_question = json.loads(quiz_question_raw)
        quiz_questions = [quiz_question]
        return render_template("quiz.html", quiz_questions=quiz_questions, subject=subject, topic=topic)
    else:
        return "Error: No agent initialized. Go to /study_guide first.", 400


@app.route("/grade_quiz", methods=["POST"])
def grade_quiz():
    data = request.get_json()

    explanation = study_guide_agent_instance.grade_quiz_question(session.get('username', "Anonymous"), json.dumps({
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


@app.route('/agent/update_study_guides', methods=["POST"])
def update_study_guides():
    data = request.get_json()
    study_guide_agent_instance.update_study_guides(data["username"], data["subject"], data["topic"], data["update"])
    return "OK", 200


@app.route("/echo", methods=["POST"])
def echo():
    text = request.get_data().decode("utf-8")
    return text, 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5005)
