from flask import Flask, render_template, request, session
import markdown

from agents.study_guide_agent import StudyGuideAgent
from model.tutor import sample_data

app = Flask(__name__)


@app.route("/")
def tutor():
    return render_template("tutor.html", subjects=sample_data.subjects)


@app.route("/study_guide")
def study_guide():
    subject = request.args.get("subject", "Unknown Subject")
    topic = request.args.get("topic", "Unknown Topic")
    username = request.args.get("username", "Anonymous")

    agent = StudyGuideAgent(username=username, subject=subject, topic=topic)
    guide_markdown = agent.invoke("Generate a study guide")
    guide_html = markdown.markdown(guide_markdown)
    return render_template("study_guide.html", topic=topic, study_guide=guide_html)


@app.route("/quiz")
def quiz():
    return render_template("quiz.html")


@app.route("/grade_quiz")
def grade_quiz():
    return render_template("grade_quiz.html")


@app.route("/new_study_guide")
def new_study_guide():
    return render_template("new_study_guide.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5005)
