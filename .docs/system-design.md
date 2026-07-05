# System Design — Interview Memory Coach

**Hackathon:** WeMakeDevs × Cognee · Jun 29–Jul 5 2026  
**Status:** Implemented and submitted Jul 5 2026

---

## 1. Requirements

### Functional

- Recruiter uploads a Job Description and candidate resume (PDF or text)
- Pre-interview fit analysis: JD↔resume match score, strengths, gaps (debounced, appears only after both fields populated)
- System auto-generates targeted interview questions from JD↔resume gap analysis
- Agent conducts a text/voice interview with SSE-streamed responses
- Every Q&A pair stored in Cognee via `remember()` per turn
- Cross-session: `recall()` surfaces prior performance for returning candidates
- Post-interview analysis: scored report (skills, gaps, recommendation score /100)
- `memify()` writes role-level question quality metadata after each session
- `forget(candidate_id)` clears all candidate data — Cognee graph + JSON sidecar (GDPR)
- Canvas-drawn interactive memory graph on the report page
- Voice input via browser MediaRecorder → Groq Whisper transcription

### Non-functional

| Concern | Target | Actual |
|---------|--------|--------|
| Streaming latency | < 200 ms first chunk | ~100 ms (Groq 300 tok/s) |
| Session start time | < 10 s | ~5 s (Cognee cognify pipeline) |
| Reliability | Single-user demo must not crash | Stable; Cognee retries are fire-and-forget |
| Auth | None | None (single-tenant, local) |
| Deployment | Single command | `uvicorn server:app --port 8000` |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Browser (static/index.html)                  │
│                                                                 │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  Intake view │   │  Interview view  │   │  Report view   │  │
│  │  JD + resume │   │  SSE chat stream │   │  Scores +      │  │
│  │  Fit analysis│   │  Voice input     │   │  Canvas graph  │  │
│  └──────┬───────┘   └────────┬─────────┘   └───────┬────────┘  │
└─────────┼────────────────────┼─────────────────────┼───────────┘
          │  REST + SSE        │                     │
┌─────────▼────────────────────▼─────────────────────▼───────────┐
│                       server.py (FastAPI)                       │
│                                                                 │
│  /api/start          /api/answer (SSE)    /api/report          │
│  /api/transcribe     /api/analyze         /api/parse-document  │
│  /api/candidates     /api/candidate/{id}/memory                │
│  /api/session/{id}/export                                       │
│  DELETE /api/candidate/{id}   /api/health                      │
└──────────┬──────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                       agents/ (Python)                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  intake.py   │  │interviewer.py│  │    analysis.py       │  │
│  │  PyMuPDF     │  │  stream_     │  │  score answers       │  │
│  │  cognify()   │  │  response()  │  │  gap analysis        │  │
│  │  questions   │  │  recall()    │  │  memify()            │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
│  base.py          memory.py          guardrails.py  voice.py   │
│  Groq client      5 Cognee APIs      sanitize()     Whisper    │
│  chat() wrapper   JSON sidecar       validate_cid()  STT       │
└──────────┬──────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│              Cognee memory layer (Cognee 1.2.2)                 │
│                                                                 │
│  cognify()    remember()    recall()    memify()    forget()    │
│                                                                 │
│  NetworkX graph store + LanceDB vector store                   │
│  (~/.cognee/ inside venv)                                       │
│                                                                 │
│  JSON sidecar: ~/.cognee_coach/sessions.json                   │
│  (structured index for deterministic lookups)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Component descriptions

### `server.py` — FastAPI backend

Holds the in-memory session store (`_sessions: dict`), routes all HTTP and SSE requests, and wires the agent functions together. No business logic lives here — it delegates to `agents/`.

SSE streaming pattern:
```python
async def event_stream():
    for chunk in _interviewer.stream_response(state, answer, idx):
        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        await asyncio.sleep(0)   # yield event loop so chunks actually flush
    asyncio.create_task(remember_qa(...))  # non-blocking memory write
    yield f"data: {json.dumps({'type': 'done', ...})}\n\n"
```

### `agents/intake.py` — session start

Receives JD text + resume text, calls `cognee.add()` + `cognee.cognify()` to build the initial entity graph, calls `recall_prior()` to load any prior session context, and generates the initial question set via the Groq LLM.

**Inputs:** `jd_text: str`, `resume_text: str`, `candidate_id: str`  
**Outputs:** `questions: list[str]`, `prior_context: dict | None`, updated state dict

### `agents/interviewer.py` — streaming dialogue

Maintains dialogue context, generates follow-up responses as a sync generator (`yield chunk`), and injects prior session context into the system prompt for returning candidates.

**Inputs:** state dict, `answer: str`, `question_idx: int`  
**Outputs:** sync generator of text chunks

### `agents/analysis.py` — post-session scoring

Reads `qa_pairs` from state, scores each answer against JD requirements using the Groq LLM, identifies skill gaps, generates a recommendation, and calls `memify()` to write role-level metadata.

**Inputs:** state dict (with completed `qa_pairs`)  
**Outputs:** `report: dict` — `{ summary, scores[], gaps[], recommendation, recommendation_score }`

### `agents/memory.py` — Cognee lifecycle

All five Cognee API wrappers plus the JSON sidecar.

| Function | Cognee call | Purpose |
|----------|-------------|---------|
| `cognify_session()` | `cognee.add()` + `cognee.cognify()` | Build entity graph from JD + resume |
| `remember_qa()` | `cognee.remember()` | Store Q&A pair per turn |
| `recall_prior()` | `cognee.recall()` | Load prior session context |
| `memify_session()` | `cognee.memify()` | Write role-level question quality |
| `forget_candidate()` | `cognee.forget()` | GDPR wipe — Cognee + sidecar |

### `agents/voice.py` — speech-to-text

```python
client.audio.transcriptions.create(
    model="whisper-large-v3",
    file=(filename, audio_bytes),
    response_format="text",
)
```

No local model download. The browser records via MediaRecorder → webm blob → `POST /api/transcribe` → Groq Whisper.

---

## 4. API reference

| Method | Endpoint | Body / Params | Returns |
|--------|----------|---------------|---------|
| `POST` | `/api/start` | multipart: `candidate_id`, `jd_text`, `resume_file?`, `resume_text?` | `{ session_id, candidate_id, questions, first_question, prior_context }` |
| `POST` | `/api/answer` | multipart: `session_id`, `answer_text` | SSE stream: `chunk` / `warning` / `done` events |
| `POST` | `/api/report` | multipart: `session_id` | `{ report }` |
| `POST` | `/api/transcribe` | multipart: `audio` (file) | `{ transcript }` |
| `POST` | `/api/analyze` | JSON: `{ jd, resume }` | `{ match_score, role_title, experience_hint, strengths[], gaps[] }` |
| `POST` | `/api/parse-document` | multipart: `file` (PDF or txt) | `{ text, char_count }` |
| `GET`  | `/api/candidates` | — | `{ candidates: [{ candidate_id, session_count, average_score }] }` |
| `GET`  | `/api/candidate/{id}/memory` | — | `{ graph: { nodes, edges }, prior_context }` |
| `GET`  | `/api/session/{id}/export` | — | `{ session_id, candidate_id, questions, qa_pairs, report }` |
| `DELETE` | `/api/candidate/{id}` | — | `{ status, candidate_id }` |
| `GET`  | `/api/health` | — | `{ status, service }` |

---

## 5. Cognee memory data model

### Graph schema

```
Candidate ──has_skill──────────> Skill
Candidate ──applied_for────────> Role
Role      ──requires_skill─────> Skill
Session   ──belongs_to─────────> Candidate
Session   ──contains───────────> QAPair
QAPair    ──assessed_by────────> Score
Score     ──flags──────────────> Skill  (gap or strength)
QuestionTemplate ──performed_well_on──> Role   (added by memify)
```

### JSON sidecar schema (`~/.cognee_coach/sessions.json`)

```json
{
  "candidate_id": {
    "sessions": [
      {
        "session_id": "sess_XXXXXX",
        "date": "2026-07-05T16:43:00",
        "report": {
          "scores": [{ "skill": "Python", "value": 4 }],
          "gaps": [{ "skill": "Distributed Systems", "description": "..." }],
          "recommendation_score": 72
        },
        "messages": [{ "role": "user|assistant|system", "content": "..." }]
      }
    ]
  }
}
```

---

## 6. Cross-session memory strategy

### Flavour 1 — Candidate memory (primary demo)

On session start, `recall_prior()` loads prior scores and gaps from both the JSON sidecar (structured) and Cognee `recall()` (semantic). The interviewer system prompt is injected with:

```
"Prior session context: [candidate] scored 2/5 on Distributed Systems.
Probe this area. Avoid repeating questions answered well in prior sessions."
```

### Flavour 2 — Role memory (implemented, partially wired)

`memify()` writes `QuestionTemplate → performed_well_on → Role` edges after each session. Data accumulates. Query-side ranking of questions by historical discrimination power is a stretch goal not yet wired into question generation.

---

## 7. Tech stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| Backend | FastAPI | `uvicorn --reload` for development |
| UI | Vanilla JS, CSS custom properties | Single file: `static/index.html` |
| LLM (agents) | Groq `llama-3.3-70b-versatile` | Direct Groq SDK, text output |
| LLM (Cognee graph) | Groq `llama-4-scout-17b-16e-instruct` | Via LiteLLM `groq/` prefix; needed for tool-call schema compliance |
| Memory | Cognee 1.2.2 | NetworkX + LanceDB defaults |
| Embeddings | FastEmbed `BAAI/bge-small-en-v1.5` | Local, no API key |
| STT | Groq Whisper `whisper-large-v3` | No local model download |
| PDF parsing | PyMuPDF (fitz) | |
| Graph viz | Canvas + vanilla JS | ~200 lines; replaced pyvis |

---

## 8. Trade-offs and known limitations

**Cognee + Groq structured output:** Cognee's internal graph extraction requires the model to include a `description` field on every node. `llama-3.3-70b-versatile` omits it; Groq rejects the tool call. Mitigated by switching Cognee's internal model to Llama 4 Scout and making `remember_qa()` fire-and-forget so retries don't block the UI. See ADR-005.

**In-memory session store:** `_sessions: dict` in `server.py` is process-scoped. Sessions are lost on server restart. For a hackathon demo this is acceptable; production would need Redis or a database.

**No auth / multi-tenancy:** Single-tenant, local. The `forget(candidate_id)` button demonstrates GDPR awareness. Called out explicitly in the README.

**`memify()` cold start:** Without real usage history, role memory (Flavour 2) shows nothing interesting. `seed_memory.py` pre-loads synthetic sessions to make `recall()` meaningful from the first demo run.

**Cognee DB migrations on first run:** The first `cognify()` call triggers 20+ Alembic migrations, adding 4–5 seconds to the first session start. Subsequent starts skip migrations and are faster. Mitigated by starting the server and immediately doing a health check (`GET /api/health`) before the demo so the migration runs before the audience is watching.
