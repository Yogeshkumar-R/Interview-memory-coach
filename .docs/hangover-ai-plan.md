# Interview Memory Coach — Build Log

**Hackathon:** WeMakeDevs × Cognee · Jun 29–Jul 5 2026  
**Use case:** UC1 — Interview Memory Coach  
**Built by:** Yogesh Kumar (solo — team of 4 planned, 1 delivered)

**Judging criteria:**
1. Depth of Cognee memory lifecycle API usage (`cognify`, `remember`, `recall`, `memify`, `forget`)
2. Polish / intuitiveness of the product experience
3. Clarity of demo, README, and submission write-up

---

## Day-by-day log

### Jun 29–30 — Setup and planning

- Confirmed Cognee + Groq baseline works locally
- Defined inter-agent state dict schema
- Wrote initial `smoke_test.py` to validate Cognee + Groq integration
- Chose raw Groq SDK over LangChain/LlamaIndex (ADR-001)
- Scaffolded `agents/` directory with `base.py`, `intake.py`, `interviewer.py`, `analysis.py`, `memory.py`

---

### Jul 1 — Core Cognee loop

- Implemented `_cognee_config()` in `agents/memory.py` — Groq via LiteLLM's `groq/` prefix, FastEmbed for local embeddings
- Implemented `cognify()` wrapper in intake agent — ingests JD + resume as a Cognee dataset
- Implemented `remember_qa()` — stores Q&A pairs per turn
- Implemented `recall_prior()` — surfaces prior session context at session start
- Implemented `forget_candidate()` — wipes Cognee graph + local sidecar
- Added JSON sidecar at `~/.cognee_coach/sessions.json` for reliable structured lookups (Cognee handles semantics; sidecar handles deterministic index)

---

### Jul 2–3 — Agents and initial Streamlit UI

- Intake agent: PyMuPDF PDF extraction, question generation from JD↔resume gap analysis
- Interviewer agent: streaming dialogue, follow-up probe logic, prior context injection into system prompt
- Analysis agent: post-session scoring, gap analysis, `memify()` call
- Guardrails: `agents/guardrails.py` — input sanitization, candidate ID validation
- Voice: `agents/voice.py` — Groq Whisper STT via Groq SDK (no local model download)
- Initial Streamlit prototype (`app.py`) — three-page navigation, file upload, chat streaming

**Pivot decision:** Streamlit was producing event loop conflicts with Cognee's async APIs and CSS injection hacks were becoming the entire UI layer. Decided to migrate to FastAPI + vanilla JS (see ADR-003).

---

### Jul 3–4 — FastAPI rewrite and glassmorphism UI

- Replaced Streamlit with FastAPI (`server.py`) + single-page app (`static/index.html`)
- Implemented SSE streaming for answer responses — `asyncio.sleep(0)` flush after each chunk
- Built new API endpoints: `/api/start`, `/api/answer`, `/api/report`, `/api/transcribe`, `/api/analyze`, `/api/parse-document`, `/api/candidates`, `/api/candidate/{id}/memory`, `/api/session/{id}/export`, `DELETE /api/candidate/{id}`
- Designed glassmorphism UI: `backdrop-filter: blur(20px)` glass panels, `#00d4ff` cyan accent, dot-grid sidebar texture, IBM Plex Mono labels
- Canvas-drawn interactive memory graph — replaced pyvis iframe entirely
- Sidebar stepper nav (Intake → Interview → Report)
- Drag-and-drop file upload with PDF parsing via `/api/parse-document`
- Voice input: MediaRecorder → Blob → Groq Whisper transcription pipeline
- Debounced fit analysis band (JD↔resume match score, hidden until both fields populated)
- Theme toggle (dark/light) via CSS custom properties + `data-theme` attribute
- Fit analysis band fixed: hidden by default, shown only after successful `/api/analyze` response

---

### Jul 5 — Cleanup, bug fixes, and submission

**Cognee + Groq structured output bug:**
- `llama-3.3-70b-versatile` consistently omits `description` field from KnowledgeGraph nodes
- Groq validates tool-call schemas server-side → rejects response → Cognee retries (8s → 16s → 32s → …)
- `remember_qa()` was blocking SSE `done` event for 60+ seconds
- Fix 1: switched `await remember_qa()` to `asyncio.create_task(remember_qa())` — fire-and-forget
- Fix 2: tried `llama-3.1-70b-versatile` — decommissioned, made things worse
- Fix 3: switched Cognee to `meta-llama/llama-4-scout-17b-16e-instruct` — Llama 4, better schema compliance

**Code cleanup:**
- Deleted `app.py` (Streamlit), root `voice.py` (local Whisper), `.claude/skills/streamlit-dev.md`
- Removed pyvis from `requirements.txt` and the dead `/api/graph/{session_id}` endpoint from `server.py`
- Removed unused `speak_text()` / pyttsx3 from `agents/voice.py`
- Updated `README.md`, `CLAUDE.md`, all `.docs/` files

**Submission checklist:**
- [x] Full demo flow runs end-to-end without crashing
- [x] `forget(candidate_id)` button visible and functional in UI
- [x] All five Cognee lifecycle APIs used: `cognify`, `remember`, `recall`, `memify`, `forget`
- [x] Canvas memory graph renders on report page
- [x] Voice input works via Groq Whisper
- [x] Fit analysis band (JD↔resume match) works with hide/show logic
- [x] Theme toggle works
- [x] README updated for FastAPI (not Streamlit)
- [x] ADR-005 written for Cognee model decision
- [ ] Backup demo video — record before submitting
- [ ] Submission writeup — explain each Cognee lifecycle call explicitly (this is scored)

---

## Key pivots from the original plan

| Planned | Actual | Why |
|---------|--------|-----|
| Anthropic SDK | Groq SDK | Speed + cost; 300 tok/s streaming |
| Streamlit UI | FastAPI + vanilla JS | Async conflicts; CSS ceiling |
| pyvis memory graph | Canvas-drawn graph | Full control; no iframe sizing hacks |
| `streamlit run app.py` | `uvicorn server:app` | Follows from UI pivot |
| Team of 4 | Solo | Team availability |
| Neo4j stretch goal | Skipped entirely | Time; pyvis already replaced by canvas |
| Local Whisper | Groq Whisper API | No model download needed |
| `llama-3.3-70b` for Cognee | `llama-4-scout` for Cognee | Schema compliance (see ADR-005) |
