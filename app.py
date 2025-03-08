from flask import Flask, render_template, request, jsonify, session
from crewai import Crew, Agent, Task, Process, LLM
import re

app = Flask(__name__)
app.secret_key = "fnknfss5s4vSvsksjnsvjs"

llm = LLM(
    model="groq/llama3-8b-8192",
    temperature=0,
    api_key="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"
)

study_path_designer = Agent(
    role="Study Path Designer",
    goal="Generate a structured study path for a specific web development topic.",
    verbose=True,
    backstory="Experienced curriculum designer specializing in web development.",
    llm=llm,
)

teacher_agent = Agent(
    role="Teacher",
    goal="Provide explanations and examples for each section of the study path.",
    verbose=True,
    backstory="Skilled teacher with expertise in explaining complex concepts.",
    llm=llm,
)

quiz_agent = Agent(
    role="Quiz Master",
    goal="Generate quizzes to test learner understanding.",
    verbose=True,
    backstory="Quiz master skilled at crafting engaging questions.",
    llm=llm,
)

generate_study_path_task = Task(
    description="Generate a structured study path for {topic} at the {user_level} level.",
    expected_output="A structured study path with chapters and sections.",
    agent=study_path_designer,
)

study_path_crew = Crew(
    agents=[study_path_designer],
    tasks=[generate_study_path_task],
    process=Process.sequential,
    verbose=True,
)


@app.route("/")
def index():
    """Render the index page."""
    return render_template("index.html")


@app.route("/study_path", methods=["GET"])
def study_path():
    """Render the study path page."""
    study_path = session.get("study_path", [])
    topic = session.get("topic", "HTML")
    user_level = session.get("user_level", "Beginner")
    return render_template("study_path.html", study_path=study_path, topic=topic, user_level=user_level)


@app.route("/generate_study_path", methods=["POST"])
def generate_study_path_view():
    """Generate the study path and store it in session."""
    topic = request.form.get("topic")
    user_level = request.form.get("user_level")

    if not topic or not user_level:
        return jsonify({"status": "error", "message": "Topic and user level are required."}), 400

    inputs = {"topic": topic, "user_level": user_level}

    try:
        study_path_crew.kickoff(inputs=inputs)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error generating study path: {str(e)}"}), 500

    study_path_output = generate_study_path_task.output
    if not study_path_output or not study_path_output.raw:
        return jsonify({"status": "error", "message": "Failed to generate the study path."})

    raw_output = study_path_output.raw

    def parse_study_path(raw_output):
        try:
            chapters = re.split(r"\*\*Chapter \d+: .*?\*\*", raw_output)[1:]
            sections = []
            for chapter in chapters:
                sections.extend(re.findall(r"Section \d+\.\d+: .*?\n", chapter))
            return [{"id": sec.split(":")[0].strip(), "title": sec.split(":")[1].strip()} for sec in sections]
        except Exception:
            return []

    parsed_sections = parse_study_path(raw_output)

    if not parsed_sections:
        return jsonify({"status": "error", "message": "No sections parsed from study path."}), 500

    session["study_path"] = parsed_sections
    session["current_section_index"] = 0
    session["topic"] = topic
    session["user_level"] = user_level

    return jsonify({"status": "success", "study_path": parsed_sections})


@app.route("/next_section", methods=["POST"])
def next_section():
    """Fetch the next section details and run teaching and quiz crews."""
    topic = session.get("topic", "")
    user_level = session.get("user_level", "")
    current_index = session.get("current_section_index", 0)
    study_path = session.get("study_path", [])

    if current_index >= len(study_path):
        # Clear session when done
        session.pop("current_section_index", None)
        session.pop("study_path", None)
        return jsonify({"status": "done", "message": "All sections completed."})

    current_section = study_path[current_index]

    teach_task = Task(
        description=f"Explain {current_section['id']}: {current_section['title']} for {topic} at {user_level} level.",
        expected_output="Explanation and examples.",
        agent=teacher_agent,
    )

    quiz_task = Task(
        description=f"Create a quiz for {current_section['id']}: {current_section['title']} to test understanding.",
        expected_output="Quiz questions.",
        agent=quiz_agent,
    )

    teaching_crew = Crew(
        agents=[teacher_agent, quiz_agent],
        tasks=[teach_task, quiz_task],
        process=Process.sequential,
    )

    try:
        teaching_crew.kickoff(inputs={"topic": topic, "user_level": user_level})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error executing section tasks: {str(e)}"}), 500

    explanation = teach_task.output.raw if teach_task.output else "No explanation available."
    quiz = quiz_task.output.raw if quiz_task.output else "No quiz available."

    session["current_section_index"] = current_index + 1

    return jsonify({
        "status": "success",
        "section": current_section,
        "explanation": explanation,
        "quiz": quiz,
    })


if __name__ == "__main__":
    app.run(debug=True)
