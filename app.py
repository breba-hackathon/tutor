from flask import Flask, render_template, request
import markdown

from agents.study_guide_agent import generate_study_guide

app = Flask(__name__)


@app.route("/")
def tutor():
    return render_template("tutor.html")


@app.route("/study_guide")
def study_guide():
    topic = request.args.get("topic", "Unknown Topic")
    guide_markdown = generate_study_guide(topic)
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
    app.run(debug=True)
