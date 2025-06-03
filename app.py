from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
import traceback
import json
from openai import OpenAI
from supabase import create_client

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def get_openai_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

QUESTIONS = [
    "What's the job title, and what are the core responsibilities in plain English?",
    "What does a typical day or week actually look like in this role — meetings, tasks, pace?",
    "Where is this role evolving over the next few years — what might change, grow, or be automated?",
    "What kind of impact or outcomes is this role truly accountable for?",
    "What have you seen go wrong in this role before — either in performance or fit?",
    "What kind of person (skills, traits, mindset) has succeeded unexpectedly in this role?",
    "What’s hard or emotionally demanding about the role — even if it’s not obvious on paper?",
    "What are some team dynamics, frictions or growth areas that this person will step into?",
    "If you could design an ideal onboarding experience, what would you do differently?",
    "What motivates someone to excel in this role — and what kind of ambition fits best?",
    "What traits or behaviours have been missing in past hires that didn’t quite work out?",
    "Would you be open to someone with an unconventional background? If so, what kind?"
]

user_sessions = {}

SYSTEM_PROMPT = """
You are the Sisuu Coach, a reflective assistant that helps hiring managers articulate the true shape of a role through thoughtful conversation. Use the user's responses to build a structured, insightful role profile. Do not create the profile until all questions are answered.
"""

FINAL_OUTPUT_INSTRUCTIONS = """
You are the Sisuu Coach. Based on the following hiring manager reflections, craft a clear, compelling role profile that helps candidates understand both the purpose of the role and the reality of what it’s like.

First, open with a strong narrative summary that describes:
- What kind of person would be a great fit
- What success looks like
- What tensions or challenges exist in the role
- Where the role is evolving

Then include:

**Key Responsibilities:** (bulleted)
**Non-negotiables:** (e.g. mindset, work ethic, specific traits)
**Working Style Breakdown:** (meetings %, deep work %, collaboration %)
**Trait Spectrum:**
- Structured vs. Dynamic
- Specialist vs. Generalist
- Entrepreneurial vs. Corporate
- Stable vs. Fast-paced
- Solo vs. Collaborative

**Transparent Expectations:** (5 bullets that describe the real experience of working in this role — cognitive/emotional demands, pace, support, communication style)

**Skills to Complement the Team:** (show gaps that this person should fill)

**Wildcard Potential:** End by asking if they'd be open to candidates with unconventional backgrounds and what that could look like.

Here’s the manager’s input:

{answers}
"""

@app.route("/chat", methods=["POST"])
def chat():
    try:
        client = get_openai_client()  # Initialize inside the route

        data = request.get_json()
        user_id = data.get("user_id")
        message = data.get("message")

        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "stage": "in_progress",
                "current_question_index": 0,
                "answers": []
            }
            return jsonify({"response": QUESTIONS[0]})

        session = user_sessions[user_id]

        if session["stage"] == "in_progress":
            index = session["current_question_index"]
            session["answers"].append(message)

            if index + 1 < len(QUESTIONS):
                session["current_question_index"] += 1
                next_question = QUESTIONS[session["current_question_index"]]
                return jsonify({"response": next_question})
            else:
                combined = "\n".join([f"Q{i+1}: {QUESTIONS[i]}\nA: {a}" for i, a in enumerate(session["answers"])])
                gpt_input = FINAL_OUTPUT_INSTRUCTIONS.format(answers=combined)

                full_response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": gpt_input}
                    ]
                )

                structured_output = full_response.choices[0].message.content.strip()
                supabase.table("role_profiles").insert({
                    "user_id": user_id,
                    "structured_output": structured_output
                }).execute()

                del user_sessions[user_id]
                return jsonify({"response": "🎉 Done! Your role profile has been created."})

    except Exception as e:
        logging.error(f"Error in /chat: {e}")
        traceback.print_exc()
        return jsonify({"response": "Something went wrong. Please try again."})

@app.route("/", methods=["GET"])
def root():
    return "Sisuu web bot is live.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

