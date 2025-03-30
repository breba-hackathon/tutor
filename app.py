import json

from flask import Flask, render_template, request, session, jsonify
import markdown

from agents.study_guide_agent import StudyGuideAgent, STUDY_GUIDE_BUILDER, QUIZ_QUESTION_BUILDER
from model.tutor import sample_data

app = Flask(__name__)

# TODO: This could be a mapping of topicId to thread_id, this would offload concurrency issues to database that keeps agent state
agent: StudyGuideAgent | None = None

@app.route("/")
def tutor():
    return render_template("tutor.html", subjects=sample_data.subjects)


@app.route("/study_guide")
def study_guide():
    global agent
    subject = request.args.get("subject", "Unknown Subject")
    topic = request.args.get("topic", "Unknown Topic")
    username = request.args.get("username", "Anonymous")

    agent = StudyGuideAgent(username=username, subject=subject, topic=topic)
    guide_markdown = agent.invoke(STUDY_GUIDE_BUILDER)
    guide_html = markdown.markdown(guide_markdown)
    return render_template("study_guide.html", topic=topic, study_guide=guide_html)


@app.route("/quiz")
def quiz():
    global agent
    if agent:
        quiz_question_raw = agent.invoke(QUIZ_QUESTION_BUILDER)
        quiz_question = json.loads(quiz_question_raw)
        quiz_questions = [ quiz_question ]
        return render_template("quiz.html", quiz_questions=quiz_questions)
    else:
        return "Error: No agent initialized. Go to /study_guide first.", 400


@app.route("/grade_quiz", methods=["POST"])
def grade_quiz():
    data = request.get_json()

    return jsonify({
        **data,
        "correct": data["selected"] == data["answer"],
        "explanation":  "Some explanation"
    })


@app.route("/new_study_guide")
def new_study_guide():
    return render_template("new_study_guide.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5005)
