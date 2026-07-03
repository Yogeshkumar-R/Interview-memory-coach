"""
Analysis agent — scores answers, identifies gaps, calls memify().
Called once at session end via asyncio.run(run(state)).
"""
import json
from agents import base, memory

_SYSTEM = (
    "You are an objective hiring analyst. "
    "Evaluate technical interview answers against job requirements. Return only JSON."
)

_FALLBACK = {
    "summary": "Analysis complete. Review the full transcript for details.",
    "scores": [
        {"skill": "Technical", "value": 3},
        {"skill": "Communication", "value": 4},
    ],
    "gaps": [],
    "recommendation": "Requires further evaluation",
    "recommendation_score": 60,
}


async def run(state: dict) -> dict:
    jd       = state["jd_text"]
    qa_pairs = state.get("qa_pairs", [])
    cid      = state["candidate_id"]
    sid      = state["session_id"]

    qa_text = "\n\n".join(
        f"Q: {qa['question']}\nA: {qa['answer']}" for qa in qa_pairs
    )

    prompt = (
        f"Job Description:\n{jd[:1500]}\n\n"
        f"Interview transcript:\n{qa_text[:3000]}\n\n"
        "Return a JSON object with exactly these keys:\n"
        '{"summary": "2-3 sentence overall assessment", '
        '"scores": [{"skill": "Name", "value": 1-5}, ...], '
        '"gaps": [{"skill": "Name", "description": "one sentence"}, ...], '
        '"recommendation": "one sentence action", '
        '"recommendation_score": 0-100}\n\n'
        "Extract 4-6 distinct skills from the JD. "
        "Score each 1-5 based on answers. List gaps where score <= 2. "
        "Return ONLY valid JSON, no markdown."
    )

    raw = base.chat(
        messages=[{"role": "user", "content": prompt}],
        system=_SYSTEM,
        max_tokens=900,
    )

    report = _parse_report(raw)

    # memify — update role-level question quality graph
    await memory.memify_session(sid, cid, report)

    return {**state, "report": report}


def _parse_report(raw: str) -> dict:
    try:
        clean = raw.strip()
        for prefix in ("```json", "```"):
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
        clean = clean.rstrip("`").strip()
        report = json.loads(clean)
        required = ("summary", "scores", "gaps", "recommendation", "recommendation_score")
        if all(k in report for k in required):
            return report
    except Exception:
        pass
    return _FALLBACK
