"""
Interviewer agent — streams follow-up responses, calls remember() per turn.
"""
from agents import base, memory

_SYSTEM = (
    "You are a sharp technical interviewer. "
    "Given the candidate's answer, respond in 2–3 sentences: acknowledge what was good, "
    "probe one specific weak point or missing detail. Be direct, not flattering. "
    "Do not ask a new question — just respond to the answer. Keep it under 80 words."
)


def stream_response(state: dict, answer: str, question_idx: int):
    """
    Sync generator for st.write_stream.
    Yields text chunks of the interviewer's reaction to the candidate's answer.
    question_idx: 0-based index of the question that elicited this answer.
    """
    jd        = state.get("jd_text", "")
    prior     = state.get("prior_context")
    questions = state.get("questions", [])

    current_q = questions[question_idx] if question_idx < len(questions) else ""

    prior_note = ""
    if prior and prior.get("note"):
        prior_note = f"Prior session context: {prior['note']}\n"

    messages = [{
        "role": "user",
        "content": (
            f"Role context (first 400 chars of JD): {jd[:400]}\n"
            f"{prior_note}"
            f"Question asked: {current_q}\n"
            f"Candidate's answer: {answer}"
        ),
    }]

    yield from base.stream_chat(messages, system=_SYSTEM, max_tokens=180)


async def remember_turn(candidate_id: str, session_id: str, question: str, answer: str):
    """Persist a Q&A pair. Called after every interview turn."""
    await memory.remember_qa(candidate_id, session_id, question, answer)
