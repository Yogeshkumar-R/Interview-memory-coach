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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

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

app = FastAPI(title="Interview Memory Coach")

Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory session store (survives for the lifetime of the process)
_sessions: dict = {}


# ── Static pages ───────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


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
        for w in warns:
            yield f"data: {json.dumps({'type': 'warning', 'content': w})}\n\n"

        # Stream the interviewer reaction chunks
        response_text = ""
        for chunk in _interviewer.stream_response(state, answer_clean, answered_count):
            response_text += chunk
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

        # Persist this turn
        state["qa_pairs"].append({"question": current_q, "answer": answer_clean})
        state["messages"].append({"role": "user", "content": answer_clean})
        state["messages"].append({"role": "assistant", "content": response_text})

        # Map-reduce if conversation is getting long
        condensed = maybe_summarize(state["messages"])
        if condensed is not state["messages"]:
            state["messages"] = condensed

        await remember_qa(state["candidate_id"], session_id, current_q, answer_clean)
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


# ── Memory graph (pyvis HTML returned for iframe embed) ────────────────────────

@app.get("/api/graph/{session_id}")
async def memory_graph(session_id: str):
    state = _sessions.get(session_id, {})
    cid = state.get("candidate_id", "candidate")
    sid = session_id
    report = state.get("report", {})

    try:
        from pyvis.network import Network
        net = Network(height="100%", width="100%", bgcolor="#080d1a", font_color="#94a3b8")
        net.set_options("""{
          "nodes": {"font": {"size": 12}, "borderWidth": 1, "shape": "dot"},
          "edges": {"smooth": {"type": "continuous"}, "font": {"size": 9, "align": "middle"},
                    "color": {"color": "rgba(100,116,139,0.5)"}},
          "physics": {"stabilization": {"iterations": 200}}
        }""")

        net.add_node(cid, label=cid, color="#00d4ff", size=24)
        net.add_node(sid, label=f"Session {sid}", color="#334155", size=16)
        net.add_edge(sid, cid, title="belongs_to", label="belongs_to")

        for score in report.get("scores", []):
            skill = score.get("skill", "")
            val = score.get("value", 0)
            color = "#10b981" if val >= 4 else "#f59e0b" if val >= 3 else "#ef4444"
            nid = f"skill_{skill.lower().replace(' ', '_')}"
            net.add_node(nid, label=f"{skill}\n{val}/5", color=color, size=14)
            net.add_edge(cid, nid, title="has_skill", label="has_skill")

        for gap in report.get("gaps", []):
            skill = gap.get("skill", "")
            nid = f"gap_{skill.lower().replace(' ', '_')}"
            if not any(n["id"] == nid for n in net.nodes):
                net.add_node(nid, label=f"Gap: {skill}", color="#ef4444", size=12)
            net.add_edge(cid, nid, title="gap", label="gap")

        graph_html = net.generate_html(notebook=False)
        return HTMLResponse(content=graph_html)
    except ImportError:
        return HTMLResponse("<p style='color:#64748b;font-family:monospace;padding:1rem'>pip install pyvis</p>")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
