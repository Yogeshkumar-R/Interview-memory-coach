# Architecture Decision Records — Interview Memory Coach

**Hackathon:** WeMakeDevs × Cognee · Jun 29–Jul 5 2026  
**Submitted:** Jul 5 2026  
**Built by:** Yogesh Kumar (solo)

---

## ADR index

| # | Title | Status |
|---|-------|--------|
| ADR-001 | Agent orchestration framework | Accepted |
| ADR-002 | Cognee storage backend | Accepted |
| ADR-003 | UI framework | Superseded — see amendment |
| ADR-004 | Cross-session memory strategy | Accepted |
| ADR-005 | Cognee internal LLM model | Accepted |

---

## ADR-001: Agent orchestration framework

**Status:** Accepted  
**Date proposed:** 2026-06-28 · **Date implemented:** 2026-07-01

### Decision

Use the **raw Groq SDK** with thin wrapper functions in `agents/base.py`. No LangChain, no LlamaIndex.

> **Amendment from proposal:** The original proposal specified the Anthropic SDK. The team switched to Groq for cost and speed — Groq's `llama-3.3-70b-versatile` is free-tier and runs at ~300 tok/s, making streaming feel instant. Cognee is separately configured to use Groq via LiteLLM's `groq/` prefix.

### Options considered

| Option | Verdict |
|--------|---------|
| Raw SDK (Groq/Anthropic) | **Chosen** — transparent, debuggable, no abstraction fighting Cognee |
| LangChain | Rejected — no first-class Cognee memory adapter; version conflicts |
| LlamaIndex | Rejected — overkill; duplicates Cognee's RAG layer |

### Consequences (actual)

- `agents/base.py` holds a shared `groq.Groq()` client and a `chat()` wrapper that handles retries
- `agents/interviewer.py` exposes a sync `stream_response()` generator consumed by the SSE endpoint
- Inter-agent state is a plain Python dict — schema defined in `CLAUDE.md`
- Streaming is SSE (`StreamingResponse` + `asyncio.sleep(0)` flush trick), not `st.write_stream()`

---

## ADR-002: Cognee storage backend

**Status:** Accepted  
**Date proposed:** 2026-06-28 · **Date confirmed:** 2026-07-01

### Decision

Use **NetworkX** (graph) + **LanceDB** (vector) — Cognee's defaults. Neo4j was not attempted.

The planned Day 5 Neo4j time-box was dropped. The pyvis graph visualisation was replaced by a **canvas-drawn interactive graph** in the UI (see ADR-003 amendment). No iframe, no pyvis dependency — the graph renderer is ~200 lines of vanilla JS that draws nodes with glow effects and supports click-to-inspect.

### Graph data flow (actual)

```
cognify()   → Cognee builds entity graph in NetworkX/LanceDB
              (stored at ~/.cognee/ inside the venv)
remember()  → Q&A pairs added to graph per turn (fire-and-forget)
recall()    → semantic query against LanceDB vectors
memify()    → role-level quality metadata added to graph

JSON sidecar (~/.cognee_coach/sessions.json)
            → structured index for deterministic lookups
              (candidate list, session history, report scores)
              Cognee is the semantic layer; sidecar is the structured layer
```

### Consequences (actual)

- Zero infra — no Docker, no credentials beyond `GROQ_API_KEY`
- `GET /api/candidate/{id}/memory` builds canvas graph data from the JSON sidecar
- pyvis dependency removed from `requirements.txt`
- The old `/api/graph/{session_id}` pyvis endpoint was removed from `server.py`

---

## ADR-003: UI framework

**Status:** Superseded — Streamlit replaced by FastAPI + vanilla JS

**Date proposed:** 2026-06-28 · **Date superseded:** 2026-07-03

### Original decision

Streamlit — `st.chat_message`, `st.chat_input`, `st.write_stream`.

### Why it was superseded

Streamlit's execution model re-runs the entire script on every interaction. This caused two concrete problems:

1. **SSE streaming friction** — Cognee's async calls inside an SSE generator conflicted with Streamlit's synchronous re-run model. `asyncio.run()` nested inside Streamlit callbacks produced event loop conflicts that were difficult to debug.
2. **UI design ceiling** — The glassmorphism design (backdrop-filter blur, canvas graph, custom sidebar stepper) required CSS that Streamlit's component system couldn't support cleanly. Injecting raw HTML/CSS via `st.markdown(unsafe_allow_html=True)` became the entire UI layer — at that point Streamlit was providing no value.

### Replacement decision

**FastAPI** backend + **vanilla JS single-page app** (`static/index.html`).

| Dimension | Streamlit | FastAPI + vanilla JS |
|-----------|-----------|----------------------|
| SSE streaming | Workaround via asyncio.run | Native StreamingResponse |
| CSS control | Inject-only, fights Streamlit | Full control |
| Canvas graph | Not possible | Native |
| Voice input | st.audio_input (1.40+) | MediaRecorder API |
| Deployment | `streamlit run app.py` | `uvicorn server:app` |
| Async agents | Event loop conflicts | Native async/await |

### Consequences (actual)

- `app.py` (Streamlit) deleted from the repo
- `server.py` is the FastAPI backend; `static/index.html` is the entire UI (~550 lines, inline CSS + JS)
- SSE streaming with `asyncio.sleep(0)` flush after each chunk
- MediaRecorder → Blob → `POST /api/transcribe` → Groq Whisper pipeline for voice input
- Typewriter animation (`setInterval` queue drain at 3 chars/20 ms) for streamed text

---

## ADR-004: Cross-session memory strategy

**Status:** Accepted — both flavours implemented  
**Date proposed:** 2026-06-28 · **Date implemented:** 2026-07-02

### Decision

Both Flavour 1 (candidate memory) and Flavour 2 (role memory via `memify()`) are implemented. Flavour 1 is the primary demo story.

### Flavour 1 — Candidate memory (demo centrepiece)

`recall(candidate_id)` returns prior session context which is injected into the interviewer system prompt. On a returning candidate's second session, the agent surfaces prior scores and skill gaps and avoids repeating answered questions.

**Implementation:** `agents/memory.py::recall_prior()` + `agents/interviewer.py` system prompt injection.

### Flavour 2 — Role memory

`memify()` is called by the analysis agent at session end, writing `QuestionTemplate → performed_well_on → Role` edges. The data accumulates across sessions.

**Status:** Data is being written correctly. Query-side question ranking using `memify()` data is a stretch goal not yet wired into question generation.

### JSON sidecar decision

An additional decision not in the original proposal: a JSON sidecar at `~/.cognee_coach/sessions.json` stores the structured session index.

**Why:** Cognee's `recall()` is a semantic search — excellent for "what were Alice's weaknesses?" but unreliable for "give me all sessions for Alice ordered by date." The sidecar provides the deterministic structured layer. Cognee provides the semantic layer.

### Consequences (actual)

- `forget(candidate_id)` wipes both Cognee graph/vectors and the JSON sidecar entry
- The UI candidate selector reads from `GET /api/candidates` → backed by the JSON sidecar
- `GET /api/candidate/{id}/memory` builds the canvas graph from sidecar data + Cognee `recall_prior()`
- Pre-seeded synthetic sessions (`seed_memory.py`) ensure `recall()` returns meaningful context during demo

---

## ADR-005: Cognee internal LLM model

**Status:** Accepted  
**Date:** 2026-07-05  
**Deciders:** Team

### Context

Cognee 1.2.2 uses an LLM internally to extract `KnowledgeGraph` structured objects from text during `cognify()` and `remember()` pipeline runs. The graph extraction prompt is sent via LiteLLM's `groq/` prefix and expects the model to call a `KnowledgeGraph` tool with a schema that requires every node to have four fields: `id`, `type`, `name`, **and `description`**.

Groq validates tool-call responses server-side. If the model omits any required field, Groq returns `tool_use_failed` rather than the (invalid) structured output, and Cognee retries with exponential backoff (8.5 s → 16.8 s → 32.7 s → …). This was first observed in session logs on 2026-07-05.

### Decision history

| Attempt | Model | Result |
|---------|-------|--------|
| 1 | `llama-3.3-70b-versatile` | Consistently omits `description` on nodes → Groq rejects tool calls, retry storm |
| 2 | `llama-3.1-70b-versatile` | Decommissioned — instant failure every attempt, worst outcome (128 s backoff wasted) |
| 3 ✓ | `meta-llama/llama-4-scout-17b-16e-instruct` | **Accepted** — Llama 4 family, improved tool-call schema compliance |

**Error from attempt 1:**
```
tool call validation failed: parameters for tool KnowledgeGraph did not match schema:
errors: [/nodes/0: missing properties: 'description', ...]
```

**Why Llama 4 Scout over alternatives:**

| Model | Reason against |
|-------|----------------|
| `llama-3.3-70b-versatile` | Confirmed schema non-compliance — omits `description` |
| `llama-3.1-70b-versatile` | Decommissioned |
| `llama-3.1-8b-instant` | Decommissioned (llama-3.1 series) |
| `gemma2-9b-it` | Good schema compliance but lower reasoning quality for graph extraction |
| `llama-3.3-70b-specdec` | Same base as attempt 1; same omission behaviour expected |
| `llama-4-maverick-17b-128e-instruct` | Same family, higher cost, no benefit for this task |

**Fallback:** If `llama-4-scout` is unavailable, use `gemma2-9b-it`.

### Consequences

- Cognee's `cognify()` and `remember()` produce valid `KnowledgeGraph` outputs without server-side rejection
- Faster inference (~400 tok/s on Groq) due to MoE architecture (17B active params, 16 experts)
- Our own agent calls (`agents/base.py`) are unaffected — they use `llama-3.3-70b-versatile` directly with text output, no tool-call schema validation

**Mitigation independent of model choice:** `remember_qa()` is called via `asyncio.create_task()` in `server.py` — fire-and-forget. Cognee retry storms never block the SSE `done` event regardless of which model is configured.
