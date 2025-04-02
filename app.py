import io
import json

import markdown
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, jsonify, send_file

from agents.study_guide_supervisor import StudyGuideSupervisorAgent
from agents.study_progress import StudyProgressAgent
from agents.user_store import default_tutor_content
from services.agent_pub_sub import start_pub_sub_consumer, StudyProgressEvent

load_dotenv()
app = Flask(__name__)
# TODO: use secret storage for this
app.secret_key = 'your-secret-key-123'

study_guide_supervisor_instance: StudyGuideSupervisorAgent = StudyGuideSupervisorAgent()
progress_agent: StudyProgressAgent = StudyProgressAgent()

# Start the pub sub consumer so that agents can listen to and publish to events
start_pub_sub_consumer()


@app.route("/")
def tutor():
    username = session.get('username', None)
    teaching_style = session.get('teaching_style', None)

    stored_tutor_content = study_guide_supervisor_instance.get_tutor_content(username)
    tutor_content = stored_tutor_content or default_tutor_content()

    return render_template(
        "tutor.html",
        subjects=tutor_content.subjects,
        username=username,
        teaching_style=teaching_style
    )


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
    subject = request.args.get("subject", "Unknown Subject")
    topic = request.args.get("topic", "Unknown Topic")
    username = session.get('username', "Anonymous")
    style = session['teaching_style']

    response = study_guide_supervisor_instance.find_existing_study_guide_or_create(username, subject, topic, style)
    if style == "textbook":
        guide_markdown = response["study_guide"]
        guide_html = markdown.markdown(guide_markdown)
        return render_template("study_guide.html", subject=subject, topic=topic, study_guide=guide_html)
    else:
        audio_file_path = response.get("audio_file_location", "")
        guide_markdown = response.get("study_guide")
        guide_html = markdown.markdown(guide_markdown)
        return render_template("audio.html", subject=subject, topic=topic, file_path=audio_file_path, text=guide_html)


@app.route("/quiz")
def quiz():
    subject = request.args.get("subject", "Unknown Subject")
    topic = request.args.get("topic", "Unknown Topic")

    if study_guide_supervisor_instance:
        quiz_question = study_guide_supervisor_instance.build_quiz_question(session.get('username', "Anonymous"))
        quiz_questions = [quiz_question]
        return render_template("quiz.html", quiz_questions=quiz_questions, subject=subject, topic=topic)
    else:
        return "Error: No agent initialized. Go to /study_guide first.", 400


@app.route("/grade_quiz", methods=["POST"])
def grade_quiz():
    data = request.get_json()

    explanation = study_guide_supervisor_instance.grade_quiz_question(session.get('username', "Anonymous"), json.dumps({
        **data,
        "correct": data["selected"] == data["answer"],
    }))

    explanation_md = markdown.markdown(explanation)
    return jsonify({
        **data,
        "correct": data["selected"] == data["answer"], "explanation": explanation_md
    })



@app.route('/audio')
def audio():
    return render_template('audio.html')


@app.route('/audio/files/<path:file_name>')
def serve_audio(file_name):
    with open(f"{file_name}", "rb") as f:
        audio_data = f.read()
    return send_file(io.BytesIO(audio_data), mimetype="audio/mpeg")


@app.route('/agent/update_progress', methods=["POST"])
def update_progress():
    data = request.get_json()
    progress_agent.inject_graded_quiz_question(data["username"], data["quiz_question"], data["subject"], data["topic"])

    return "OK", 200


@app.route('/agent/update_study_guides', methods=["POST"])
def update_study_guides():
    data = request.get_json()
    event = StudyProgressEvent(**data)
    study_guide_supervisor_instance.update_study_guides(event)
    return "OK", 200


@app.route("/echo", methods=["POST"])
def echo():
    text = request.get_data().decode("utf-8")
    return text, 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5005)
