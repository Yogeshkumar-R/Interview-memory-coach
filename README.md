# Interview Memory Coach

> **WeMakeDevs × Cognee Hackathon** — Jun 29–Jul 5 2026

An AI-powered interviewer that **remembers candidates across sessions** using Cognee's full memory lifecycle. Upload a job description and resume, run a live streaming interview, get a scored report — and every session is stored so the next interview picks up exactly where the last one left off.

---

## Demo flow



```
Upload JD + Resume
        │
        ▼  cognify() — builds entity graph from JD + resume
  AI Interview (streaming)
        │
        ├─ recall() at session start → surfaces prior performance
        └─ remember() each turn    → stores Q&A pairs live
        │
        ▼
  Scored Report + Canvas Memory Graph
        │
        └─ memify() — writes role-level quality metadata
           forget() — GDPR wipe button
```
📺 Video Demo

🎬 Watch the Project Walkthrough
What's covered in the video:

Hackathon Overview & Problem Statement

Uploading JDs/Resumes & cognify() Graph Building

Live Streaming Interview & Real-Time remember() Hooks

Cross-Session Persistence: Deep Dive into recall()

Interactive Canvas Memory Graph & The GDPR forget() Wipe

**Video Link :** https://youtu.be/wDEWcbQSrMI?si=buKZGeKTMJT7nlDq
---

## Quick start

**Prerequisites:** Python 3.10+, a [Groq API key](https://console.groq.com)

```bash
# 1. Clone
git clone <repo-url>
cd Interview-memory-coach

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env → GROQ_API_KEY=gsk_...

# 4. Run
uvicorn server:app --reload --port 8000
# Open http://localhost:8000
```

---

## Project structure

```
Interview-memory-coach/
├── server.py              # FastAPI backend — all API endpoints
├── static/
│   └── index.html         # Single-page glassmorphism UI (vanilla JS, no framework)
│
├── agents/
│   ├── base.py            # Groq client + retry wrapper
│   ├── intake.py          # Parse JD + resume → cognify() → question generation
│   ├── interviewer.py     # Streaming dialogue + remember() per turn
│   ├── analysis.py        # Post-session scoring + memify()
│   ├── memory.py          # All five Cognee lifecycle wrappers + JSON sidecar
│   ├── guardrails.py      # Input sanitization + candidate ID validation
│   └── voice.py           # Groq Whisper STT via the Groq SDK
│
├── requirements.txt
├── .env.example
└── CLAUDE.md              # Developer notes
```

---

## Architecture

Three layers: **FastAPI + vanilla JS UI → Groq LLM agents → Cognee memory**

```
Browser (index.html)
  │  SSE streaming + REST JSON
  ▼
server.py (FastAPI)
  ├── /api/start        → intake.run()       → cognify()
  ├── /api/answer       → interviewer        → remember() per turn
  ├── /api/report       → analysis.run()     → memify()
  ├── /api/transcribe   → voice.transcribe_audio()
  ├── /api/analyze      → LLM fit analysis   (JD ↔ resume match score)
  ├── /api/parse-document → PyMuPDF text extraction
  ├── /api/candidates   → JSON sidecar list
  ├── /api/candidate/{id}/memory → canvas graph data
  └── /api/candidate/{id} DELETE → forget()

agents/memory.py
  ├── cognify()    — entity graph from JD + resume
  ├── remember()   — Q&A pair stored per turn
  ├── recall()     — prior session context at start
  ├── memify()     — role-level quality graph update
  └── forget()     — GDPR wipe (Cognee + JSON sidecar)
```

**LLM:** `llama-3.3-70b-versatile` via Groq for agents · `llama-4-scout-17b-16e-instruct` via Groq for Cognee's internal graph extraction (see ADR-003)  
**Embeddings:** FastEmbed `BAAI/bge-small-en-v1.5` (local, no API key)  
**Memory store:** Cognee (NetworkX graph + LanceDB vector, `~/.cognee/`) + JSON sidecar (`~/.cognee_coach/sessions.json`)

---

## Cognee memory lifecycle

All five Cognee APIs are used — this is the core of the submission:

| API | Where | What it does |
|-----|-------|--------------|
| `cognify()` | Intake agent | Parses JD + resume into a knowledge graph (Candidate, Skills, Role entities). Graph persists across sessions. |
| `remember()` | Interviewer — every turn | Stores each Q&A pair into the candidate's memory graph in real time as the interview progresses. |
| `recall(candidate_id)` | Interviewer — session start | Retrieves prior session context (past scores, skill gaps) so the AI probes known weak areas and doesn't repeat questions. |
| `memify()` | Analysis agent — session end | Writes role-level quality metadata back (`QuestionTemplate → performed_well_on → Role`) so future sessions for the same role improve. |
| `forget(candidate_id)` | Report page — UI button | GDPR: wipes the candidate's entire Cognee graph and local sidecar. Visible in every demo run. |

### Memory graph schema

```
Candidate ──has_skill──────────> Skill
Candidate ──applied_for────────> Role
Role      ──requires_skill─────> Skill
Session   ──belongs_to─────────> Candidate
Session   ──contains───────────> QAPair
QAPair    ──assessed_by────────> Score
Score     ──flags──────────────> Skill  (gap or strength)
QuestionTemplate ──performed_well_on──> Role   (via memify)
```

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/start` | Begin a session (multipart: candidate_id, jd_text, resume_file/resume_text) |
| `POST` | `/api/answer` | Submit an answer → SSE stream of `chunk` / `done` events |
| `POST` | `/api/report` | Generate scored report for a completed session |
| `POST` | `/api/transcribe` | Transcribe audio via Groq Whisper |
| `POST` | `/api/analyze` | Fit analysis: JD ↔ resume match score + strengths/gaps |
| `POST` | `/api/parse-document` | Extract text from PDF or plain text file |
| `GET`  | `/api/candidates` | List all candidates with session counts |
| `GET`  | `/api/candidate/{id}/memory` | Graph nodes/edges + prior session context |
| `GET`  | `/api/session/{id}/export` | Export session JSON (questions, Q&A pairs, report) |
| `DELETE` | `/api/candidate/{id}` | GDPR forget — deletes candidate from Cognee + sidecar |
| `GET`  | `/api/health` | Health check |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| UI | Vanilla JS, glassmorphism CSS, canvas-drawn memory graph |
| Backend | FastAPI + SSE streaming |
| LLM (agents) | Groq SDK — `llama-3.3-70b-versatile` |
| LLM (Cognee graph) | Groq — `llama-4-scout-17b-16e-instruct` (structured output compliant) |
| Memory | Cognee 1.2.2 — NetworkX graph + LanceDB vector store |
| Embeddings | FastEmbed `BAAI/bge-small-en-v1.5` (local) |
| STT | Groq Whisper (`whisper-large-v3`) via Groq SDK |
| PDF parsing | PyMuPDF (fitz) |

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key from console.groq.com |

Memory is stored locally — no external database required.
