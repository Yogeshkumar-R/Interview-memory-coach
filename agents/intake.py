"""
Intake agent — parses JD + resume, builds Cognee entity graph, generates questions.
Called once at session start via asyncio.run(run(state)).
"""
import json
from agents import base, memory

_SYSTEM = (
    "You are an expert technical interviewer. "
    "Generate targeted interview questions that reveal true depth, not rehearsed answers."
)


async def run(state: dict) -> dict:
    jd     = state["jd_text"]
    resume = state["resume_text"]
    cid    = state["candidate_id"]
    sid    = state["session_id"]

    # 1. cognify — build entity graph
    await memory.cognify_session(jd, resume, cid, sid)

    # 2. recall — load prior context
    prior = await memory.recall_prior(cid)

    # 3. generate questions
    prior_note = ""
    if prior and prior.get("last_session", {}).get("qa_pairs"):
        prior_note = (
            f"\n\nPrior session note: {prior['note']} "
            "Do NOT repeat questions the candidate already answered."
        )

    prompt = (
        f"Job Description:\n{jd}\n\n"
        f"Resume:\n{resume[:3000]}"
        f"{prior_note}\n\n"
        "Generate exactly 5 targeted interview questions as a JSON array of strings. "
        "Probe: technical depth, gaps between JD requirements and resume claims, "
        "concrete past experience. Return ONLY a valid JSON array. No other text."
    )

    raw = base.chat(
        messages=[{"role": "user", "content": prompt}],
        system=_SYSTEM,
        max_tokens=600,
    )

    questions = _parse_questions(raw)

    return {
        **state,
        "questions":          questions,
        "prior_context":      prior,
        "extracted_entities": {"jd_len": len(jd), "resume_len": len(resume)},
    }


def _parse_questions(raw: str) -> list[str]:
    try:
        clean = raw.strip()
        for prefix in ("```json", "```"):
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
        clean = clean.rstrip("`").strip()
        qs = json.loads(clean)
        if isinstance(qs, list) and qs:
            return [str(q) for q in qs[:5]]
    except Exception:
        pass
    # fallback: extract lines with a "?"
    lines = [l.strip().lstrip("0123456789.-) ") for l in raw.splitlines() if "?" in l]
    return lines[:5] or ["Tell me about your background and how it relates to this role."]
