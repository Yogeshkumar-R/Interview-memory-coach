"""
FastAPI backend for Interview Memory Coach.
Replaces Streamlit with a proper chat-style UI.

Run:  uvicorn server:app --reload --port 8000
Then: open http://localhost:8000
"""
import json
import os
import uuid
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from agents import analysis as _analysis
from agents import intake as _intake
from agents import interviewer as _interviewer
from agents.guardrails import sanitize, validate_candidate_id
from agents.memory import (
    _cognee_config,
    forget_candidate,
    get_candidate_profile,
    maybe_summarize,
    remember_qa,
    save_chat_history,
)
from agents.voice import transcribe_audio

_cognee_config()

# API schema endpoints are only exposed in development.
# Set APP_ENV=staging or APP_ENV=production to hide them.
_is_dev = os.getenv("APP_ENV", "development").lower() == "development"

app = FastAPI(
    title="Interview Memory Coach",
    docs_url="/dev/swagger" if _is_dev else None,
    redoc_url="/dev/redoc"   if _is_dev else None,
    openapi_url="/dev/openapi.json" if _is_dev else None,
)

Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory session store (survives for the lifetime of the process)
_sessions: dict = {}

# Strong references to fire-and-forget background tasks.
# asyncio holds only a weak ref to tasks; without this set, CPython's GC can
# collect a task before it completes, silently dropping Cognee writes.
_background_tasks: set = set()


# ── Static pages ───────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/docs", include_in_schema=False)
async def docs_page():
    return FileResponse("static/docs.html")


# ── Session start ──────────────────────────────────────────────────────────────

@app.post("/api/start")
async def start_session(
    candidate_id: str = Form(...),
    jd_text: str = Form(...),
    resume_file: Optional[UploadFile] = File(None),
    resume_text: str = Form(""),
):
    cid_valid, cid_err = validate_candidate_id(candidate_id)
    if not cid_valid:
        raise HTTPException(status_code=400, detail=cid_err)

    jd_clean, _ = sanitize(jd_text, "jd")

    # PDF upload takes precedence over pasted text
    if resume_file and resume_file.filename:
        try:
            pdf_bytes = await resume_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            raw_resume = "\n".join(p.get_text() for p in doc)
        except Exception:
            raw_resume = resume_text or "[Could not parse PDF]"
    else:
        raw_resume = resume_text

    resume_clean, _ = sanitize(raw_resume, "resume")

    session_id = f"sess_{uuid.uuid4().hex[:6].upper()}"
    state = {
        "session_id": session_id,
        "candidate_id": candidate_id.strip(),
        "jd_text": jd_clean,
        "resume_text": resume_clean,
        "extracted_entities": {},
        "questions": [],
        "qa_pairs": [],
        "prior_context": None,
        "report": None,
        "messages": [],
        "interview_ended": False,
    }

    state = await _intake.run(state)
    _sessions[session_id] = state

    prior = state.get("prior_context")
    return JSONResponse({
        "session_id": session_id,
        "candidate_id": candidate_id.strip(),
        "questions": state["questions"],
        "first_question": state["questions"][0] if state["questions"] else "",
        "prior_context": {
            "note": prior.get("note", ""),
            "session_date": prior.get("session_date", ""),
        } if prior else None,
    })


# ── Answer + streaming interviewer response ────────────────────────────────────

@app.post("/api/answer")
async def answer_stream(
    session_id: str = Form(...),
    answer_text: str = Form(...),
):
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    answer_clean, warns = sanitize(answer_text, "answer")
    if not answer_clean:
        raise HTTPException(status_code=400, detail="Empty answer after sanitization")

    qa_pairs = state.get("qa_pairs", [])
    questions = state.get("questions", [])
    answered_count = len(qa_pairs)

    if answered_count >= len(questions):
        raise HTTPException(status_code=400, detail="All questions already answered")

    current_q = questions[answered_count]
    is_last = (answered_count + 1) >= len(questions)
    next_q = None if is_last else questions[answered_count + 1]

    async def event_stream():
        import asyncio
        for w in warns:
            yield f"data: {json.dumps({'type': 'warning', 'content': w})}\n\n"

        # asyncio.sleep(0) yields control back to the event loop so each SSE
        # chunk is actually flushed to the client before the next is produced.
        response_text = ""
        try:
            for chunk in _interviewer.stream_response(state, answer_clean, answered_count):
                response_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0)
        finally:
            # Persist this turn whether or not the client is still connected.
            # Using finally ensures a mid-stream disconnect doesn't silently
            # lose the Q&A pair from both the session state and the JSON sidecar.
            state["qa_pairs"].append({"question": current_q, "answer": answer_clean})
            state["messages"].append({"role": "user", "content": answer_clean})
            state["messages"].append({"role": "assistant", "content": response_text})

            condensed = maybe_summarize(state["messages"])
            if condensed is not state["messages"]:
                state["messages"] = condensed

            # Store the task reference so CPython's GC can't collect it before
            # remember_qa completes (asyncio holds only a weak ref otherwise).
            task = asyncio.create_task(
                remember_qa(state["candidate_id"], session_id, current_q, answer_clean)
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

            save_chat_history(state["candidate_id"], session_id, state["messages"])

        yield f"data: {json.dumps({'type': 'done', 'next_question': next_q, 'interview_ended': is_last})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Voice transcription ────────────────────────────────────────────────────────

@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    filename = audio.filename or "audio.webm"
    transcript = transcribe_audio(audio_bytes, filename)
    return JSONResponse({"transcript": transcript})


# ── Report generation ──────────────────────────────────────────────────────────

@app.post("/api/report")
async def generate_report(session_id: str = Form(...)):
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    state = await _analysis.run(state)
    _sessions[session_id] = state
    return JSONResponse({"report": state.get("report", {})})


# ── GDPR forget ────────────────────────────────────────────────────────────────

@app.delete("/api/candidate/{candidate_id}")
async def forget(candidate_id: str):
    cid_valid, cid_err = validate_candidate_id(candidate_id)
    if not cid_valid:
        raise HTTPException(status_code=400, detail=cid_err)
    await forget_candidate(candidate_id)
    return JSONResponse({"status": "deleted", "candidate_id": candidate_id})


# ── Candidate profile ──────────────────────────────────────────────────────────

@app.get("/api/profile/{candidate_id}")
async def profile(candidate_id: str):
    return JSONResponse(get_candidate_profile(candidate_id))


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "service": "Interview Memory Coach",
        "env": os.getenv("APP_ENV", "development"),
        "swagger": "/dev/swagger" if _is_dev else None,
    })


# ── Candidates list ────────────────────────────────────────────────────────────

@app.get("/api/candidates")
async def list_candidates():
    from agents.memory import _load
    store = _load()
    result = []
    for cid, data in store.items():
        sessions = data.get("sessions", [])
        scores_flat = []
        for s in sessions:
            for sc in s.get("report", {}).get("scores", []):
                raw = sc.get("value") if sc.get("value") is not None else sc.get("score")
                try:
                    scores_flat.append(float(raw))
                except (TypeError, ValueError):
                    pass
        result.append({
            "candidate_id": cid,
            "session_count": len(sessions),
            "average_score": round(sum(scores_flat) / len(scores_flat), 1) if scores_flat else None,
        })
    return JSONResponse({"candidates": result})


# ── Candidate memory graph ─────────────────────────────────────────────────────

@app.get("/api/candidate/{candidate_id}/memory")
async def candidate_memory(candidate_id: str):
    from agents.memory import _load
    store = _load()
    data = store.get(candidate_id, {})
    sessions = data.get("sessions", [])

    nodes: list = []
    edges: list = []
    cnode = f"candidate:{candidate_id}"
    nodes.append({"id": cnode, "label": candidate_id, "group": "Candidate",
                  "detail": f"Candidate: {candidate_id}, {len(sessions)} session(s)"})

    for s in sessions:
        sid = s.get("session_id", "")
        if not sid:
            continue
        snode = f"session:{sid}"
        nodes.append({"id": snode, "label": sid[-6:], "group": "Session",
                       "detail": f"Session {sid}, {s.get('date', 'date unknown')}"})
        edges.append({"from": snode, "to": cnode, "label": "belongs_to"})

        for score in s.get("report", {}).get("scores", []):
            skill = score.get("skill", "")
            if not skill:
                continue
            nid = f"skill:{skill.lower().replace(' ', '_')}"
            if not any(n["id"] == nid for n in nodes):
                val = score.get("value", score.get("score", "?"))
                nodes.append({"id": nid, "label": skill, "group": "Skill",
                               "detail": f"Skill: {skill}  —  {val}/5"})
            if not any(e["from"] == cnode and e["to"] == nid for e in edges):
                edges.append({"from": cnode, "to": nid, "label": "has_skill"})

        for gap in s.get("report", {}).get("gaps", []):
            skill = gap.get("skill", "")
            if not skill:
                continue
            nid = f"gap:{skill.lower().replace(' ', '_')}"
            if not any(n["id"] == nid for n in nodes):
                nodes.append({"id": nid, "label": skill, "group": "Gap",
                               "detail": f"Gap: {skill} — {gap.get('description', '')}"})
            if not any(e["from"] == cnode and e["to"] == nid for e in edges):
                edges.append({"from": cnode, "to": nid, "label": "gap"})

    prior_sessions = [
        {"scores": s.get("report", {}).get("scores", []),
         "gaps":   s.get("report", {}).get("gaps", [])}
        for s in sessions
    ]
    return JSONResponse({
        "graph": {"nodes": nodes, "edges": edges},
        "prior_context": {"sessions": prior_sessions} if prior_sessions else None,
    })


# ── Fit analysis ───────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    jd: str
    resume: str


@app.post("/api/analyze")
async def analyze_fit(req: AnalyzeRequest):
    from agents.base import chat as _chat
    prompt = (
        "Analyze the fit between this job description and resume. "
        "Return ONLY valid JSON with exactly these fields:\n"
        '{"match_score": <integer 0-100>, "role_title": "<string>", '
        '"experience_hint": "<string>", "strengths": ["<skill>", ...], '
        '"gaps": ["<skill>", ...]}\n\n'
        f"JD:\n{req.jd[:2000]}\n\nResume:\n{req.resume[:2000]}"
    )
    try:
        raw = _chat(
            messages=[{"role": "user", "content": prompt}],
            system="Return only valid JSON. No markdown. No extra text.",
            max_tokens=350,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return JSONResponse(json.loads(raw.strip()))
    except Exception as exc:
        print(f"[analyze] {exc}")
        return JSONResponse({
            "match_score": 50, "role_title": "Role",
            "experience_hint": "unknown", "strengths": [], "gaps": [],
        })


# ── Document parsing ───────────────────────────────────────────────────────────

@app.post("/api/parse-document")
async def parse_document(file: UploadFile = File(...)):
    content = await file.read()
    filename = (file.filename or "").lower()
    try:
        if filename.endswith(".pdf"):
            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n".join(p.get_text() for p in doc)
        else:
            text = content.decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse document: {exc}")
    return JSONResponse({"text": text.strip(), "char_count": len(text)})


# ── Session export ─────────────────────────────────────────────────────────────

@app.get("/api/session/{session_id}/export")
async def export_session(session_id: str):
    s = _sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse({
        "session_id": session_id,
        "candidate_id": s.get("candidate_id"),
        "questions": s.get("questions", []),
        "qa_pairs": s.get("qa_pairs", []),
        "report": s.get("report"),
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
