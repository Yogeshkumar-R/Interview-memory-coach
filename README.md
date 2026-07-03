# Interview Memory Coach

> WeMakeDevs × Cognee Hackathon — Jun 29–Jul 5 2026

An AI-powered interview system that **remembers candidates across sessions** using Cognee's memory lifecycle APIs. Upload a job description and resume, run a live streaming interview, get a scored report — and every session is stored so the next interview picks up exactly where the last one left off.

---

## Demo flow

```
Upload JD + Resume  →  AI Interview (streaming)  →  Scored Report + Memory Graph
                                ↑
              Cognee recalls prior session context at start
```

---

## Setup

**Prerequisites:** Python 3.10+, a [Groq API key](https://console.groq.com)

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd Interview-memory-coach-

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Groq API key
cp .env.example .env
# Edit .env and add your key: GROQ_API_KEY=gsk_...

# 4. Seed synthetic memory (pre-loads 2 prior sessions so recall() has data)
python seed_memory.py

# 5. Run the app
streamlit run app.py
```

To verify your environment before the first run:

```bash
python smoke_test.py
```

---

## Folder structure

```
Interview-memory-coach-/
├── app.py                   # Streamlit UI — three-page navigation
├── seed_memory.py           # Pre-loads synthetic candidate sessions
├── smoke_test.py            # Environment validation (run before demo)
├── requirements.txt
├── .env.example             # Template — copy to .env and fill in key
│
├── agents/
│   ├── base.py              # Groq client, retry wrapper, streaming helper
│   ├── intake.py            # Parse JD + resume, cognify(), generate questions
│   ├── interviewer.py       # Streaming responses, remember() per turn
│   ├── analysis.py          # Score answers, gap analysis, memify()
│   └── memory.py            # All five Cognee lifecycle wrappers
│
└── .claude/
    ├── agents/              # Claude Code sub-agent definitions
    └── skills/              # Claude Code skill definitions
```

---

## Architecture

Three-layer stack: **Streamlit UI → Groq LLM agents → Cognee memory**

```
app.py
  └─ page: "upload"     → intake.run()       → cognify()
  └─ page: "interview"  → interviewer         → remember() each turn
                                              → recall() at session start
  └─ page: "report"     → analysis.run()     → memify()
                          forget button       → forget()

                                    Cognee memory layer
                         (NetworkX graph + LanceDB vector, ~/.cognee/)
```

**LLM:** `llama-3.3-70b-versatile` via Groq (routed through LiteLLM's `groq/` prefix)  
**Embeddings:** FastEmbed `BAAI/bge-small-en-v1.5` (local, no API key required)

---

## Cognee memory lifecycle

All five Cognee lifecycle APIs are used — this is the core of the submission:

| API | Where | What it does |
|-----|-------|--------------|
| `cognify()` | Intake agent | Parses the JD + resume text into a knowledge graph of entities (Candidate, Skills, Role). This graph persists across sessions. |
| `remember()` | Interviewer agent — every turn | Stores each Q&A pair into the candidate's memory graph in real time as the interview progresses. |
| `recall(candidate_id)` | Interviewer agent — session start | Retrieves prior session context (past scores, skill gaps, answered questions) so the AI doesn't repeat itself and can probe known weak areas. |
| `memify()` | Analysis agent — session end | Writes role-level quality metadata back to the graph (`QuestionTemplate → performed_well_on → Role`) so future sessions for the same role improve. |
| `forget(candidate_id)` | Report page — UI button | GDPR compliance: wipes the candidate's entire graph and local sidecar. Visible in every demo run. |

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

## Tech stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit — `st.write_stream()` for live streaming |
| LLM | Groq SDK — `llama-3.3-70b-versatile` |
| Memory | Cognee — NetworkX graph + LanceDB vector store |
| Embeddings | FastEmbed — local `BAAI/bge-small-en-v1.5` |
| PDF parsing | PyMuPDF (fitz) |
| Graph viz | pyvis — embedded in report page |

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Your Groq API key from console.groq.com |

Memory is stored locally at `~/.cognee_coach/sessions.json` (structured sidecar) and `~/.cognee/` (Cognee graph + vectors). No external database required.
