# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project overview

**Interview Memory Coach** — hackathon submission (WeMakeDevs × Cognee, Jun 29–Jul 5 2026).  
An AI-powered interview system that remembers candidates across sessions using Cognee's memory lifecycle APIs.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
uvicorn server:app --reload --port 8000
# Open http://localhost:8000
```

## Architecture

Three-layer stack: **FastAPI + vanilla JS UI → Groq LLM agents → Cognee memory**

```
Browser (static/index.html)   — glassmorphism SPA, vanilla JS, canvas graph
        │  REST + SSE
        ▼
server.py (FastAPI)            — routing, session store, SSE streaming
        │
        ├── agents/intake.py   → cognify() — entity graph from JD + resume
        ├── agents/interviewer.py → stream_response() + remember() per turn
        ├── agents/analysis.py → scoring + memify()
        ├── agents/memory.py   → all five Cognee lifecycle wrappers + JSON sidecar
        ├── agents/voice.py    → Groq Whisper STT
        └── agents/guardrails.py → input sanitization
```

## Inter-agent state dict schema

```python
{
    "session_id": str,
    "candidate_id": str,
    "jd_text": str,
    "resume_text": str,
    "extracted_entities": dict,   # set by intake
    "questions": list[str],       # set by intake
    "qa_pairs": list[dict],       # appended per answer turn
    "prior_context": dict | None, # set by recall() at session start
    "report": dict | None,        # set by analysis agent
    "messages": list[dict],       # full chat history (role/content)
    "interview_ended": bool,
}
```

## Key implementation details

- **SSE streaming:** `POST /api/answer` returns a `StreamingResponse` with `text/event-stream`.  
  Each event is `data: {"type": "chunk"|"warning"|"done", ...}\n\n`.  
  `asyncio.sleep(0)` after each chunk yields the event loop so chunks actually flush.

- **remember_qa is fire-and-forget:** Called via `asyncio.create_task()` inside the SSE generator  
  so Cognee's internal retries (Groq schema validation issues) don't block the `done` event.

- **Cognee + Groq structured output:** Cognee 1.2.2 uses `llama-4-scout-17b-16e-instruct` via the  
  `groq/` LiteLLM prefix (see ADR-005). The model must produce `description` on every  
  KnowledgeGraph node or Groq's tool-call validator rejects the response and Cognee retries  
  with exponential backoff. `remember_qa` is also called via `asyncio.create_task()` with a  
  strong reference stored in `_background_tasks` so the task isn't GC'd mid-run.

- **JSON sidecar:** `~/.cognee_coach/sessions.json` is the reliable structured store used by  
  `/api/candidates`, `/api/candidate/{id}/memory`, and cross-session recall.  
  Cognee's graph/vector layer is the semantic layer for `remember()`/`recall()`.

- **Canvas graph:** The memory graph in the UI is drawn on a `<canvas>` element — no pyvis,  
  no iframes. Node data comes from `GET /api/candidate/{id}/memory`.

## Cognee lifecycle calls

| Call | Where | Purpose |
|------|-------|---------|
| `cognify()` | intake.py | Build entity graph from JD + resume |
| `remember()` | memory.py `remember_qa()` | Store each Q&A pair per turn |
| `recall()` | memory.py `recall_prior()` | Surface prior performance at session start |
| `memify()` | analysis.py | Update role-level question quality graph |
| `forget()` | memory.py `forget_candidate()` | GDPR — must stay in final build |

## Rules

- Do not add Streamlit, LangChain, or LlamaIndex dependencies.
- `forget(candidate_id)` must remain visible and functional in the UI — judges score on it.
- All five Cognee lifecycle APIs must be used in the submission.
- The JSON sidecar is the reliable data source; Cognee is the semantic enrichment layer.
