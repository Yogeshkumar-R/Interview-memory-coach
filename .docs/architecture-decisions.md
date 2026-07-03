# Architecture Decision Records — Interview Memory Coach (UC1)

**Hackathon:** WeMakeDevs × Cognee · Jun 29 – Jul 5 2026
**Team size:** 4 · **Available time:** ~25 hrs total

---

## ADR index

| # | Title | Status |
|---|---|---|
| ADR-001 | Agent orchestration framework | Proposed |
| ADR-002 | Cognee storage backend | Proposed |
| ADR-003 | UI framework | Proposed |
| ADR-004 | Cross-session memory strategy | Proposed |

---

## ADR-001: Agent orchestration framework

**Status:** Proposed
**Date:** 2026-06-28
**Deciders:** Full team (affects everyone's day-to-day coding)

### Context

Three agents need to be orchestrated — Intake, Interviewer, and Analysis — each calling the Anthropic API, reading/writing Cognee, and passing state between them. The choice here determines how fast the team can iterate, how easy debugging is, and how much boilerplate eats into the available 25 hours.

### Decision

Use the **raw Anthropic Python SDK** with thin wrapper functions, not a framework like LangChain or LlamaIndex.

### Options considered

#### Option A: Raw Anthropic SDK + custom wrappers

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Setup time | ~30 min |
| Debugging | Excellent — plain Python tracebacks |
| Team familiarity | High (it's just API calls) |
| Cognee integration | Manual but transparent |

**Pros:**
- No abstraction layer hiding what's happening
- Cognee calls sit right next to Claude calls in the same function
- Zero dependency conflicts
- Easy to demo step-by-step with full visibility

**Cons:**
- More boilerplate: retry logic, streaming, message history management must be written manually
- Each agent is a plain function that needs to be wired together explicitly

#### Option B: LangChain

| Dimension | Assessment |
|---|---|
| Complexity | Medium–High |
| Setup time | 2–3 hrs to get chains + memory adapters right |
| Debugging | Poor — errors buried in abstraction layers |
| Team familiarity | Variable |
| Cognee integration | Requires a custom `BaseMemory` adapter |

**Pros:**
- Built-in agent loop
- Tool calling abstractions
- Many tutorials online

**Cons:**
- Cognee has no first-class LangChain memory adapter — writing one is a rabbit hole
- LangChain's `AgentExecutor` fights with Cognee's async API
- Version conflicts between `langchain`, `langchain-anthropic`, and `cognee` are common and time-consuming

#### Option C: LlamaIndex

| Dimension | Assessment |
|---|---|
| Complexity | High |
| Setup time | 3–4 hrs |
| Debugging | Poor |
| Team familiarity | Low (typically) |
| Cognee integration | No native support |

**Pros:**
- Strong RAG primitives

**Cons:**
- Overkill — Cognee is already the RAG layer. Two overlapping memory systems confuse both the architecture and the judges.

### Trade-off analysis

The core tension is **productivity vs. features**. LangChain provides an agent loop out of the box but the first day would be spent fighting its Cognee integration rather than building the actual product. The raw SDK gives nothing for free, but everything written is fully owned, debuggable, and demo-friendly.

For a hackathon where the demo is everything and 25 hours is the budget, **transparent and debuggable beats feature-rich and opaque**.

### Consequences

- Each agent is a Python `async def` function accepting a `messages: list` parameter
- State is passed between agents as plain dicts — agreed schema on Day 1
- A ~20-line retry wrapper for rate limit errors will need to be hand-written in `agents/base.py`
- Streaming to the Streamlit UI uses `anthropic.messages.stream()` + `st.write_stream()`

### Action items

- [ ] Person 2 creates `agents/base.py` with shared client, retry wrapper, and streaming helper on Day 1
- [ ] Full team agrees on the inter-agent state dict schema before anyone writes an agent

---

## ADR-002: Cognee storage backend

**Status:** Proposed
**Date:** 2026-06-28
**Deciders:** Person 1 (Cognee integration lead)

### Context

Cognee supports multiple graph and vector backends. The choice affects setup time, demo reliability, and how inspectable the memory graph is during the demo. Showing a populated graph to judges is a strong visual signal.

### Decision

Use **NetworkX** (graph) + **LanceDB** (vector) — Cognee's defaults — for the hackathon. Do not swap to Neo4j or Weaviate unless there is a specific demo need and time allows.

### Options considered

#### Option A: NetworkX + LanceDB (Cognee defaults)

| Dimension | Assessment |
|---|---|
| Setup time | Zero — works out of the box |
| Persistence | File-backed (LanceDB on disk, NetworkX pickled to `~/.cognee/`) |
| Query capability | Sufficient for hackathon queries |
| Demo visibility | Low natively; exportable to pyvis for visualisation |
| Production readiness | No |

**Pros:**
- No Docker, no credentials, no connection strings
- `cognee.cognify()` works immediately after `pip install cognee`
- LanceDB persists automatically

**Cons:**
- Graph is not browsable via a GUI without extra work
- NetworkX doesn't scale past ~100K nodes (irrelevant for this project)

#### Option B: Neo4j + Weaviate

| Dimension | Assessment |
|---|---|
| Setup time | 2–4 hrs (Docker Compose, credentials, Cognee config) |
| Persistence | Production-grade |
| Query capability | Cypher queries, Weaviate hybrid search |
| Demo visibility | Neo4j Browser is excellent for live graph visualisation |
| Production readiness | Yes |

**Pros:**
- Neo4j Browser running live during a demo is genuinely impressive — the candidate entity graph populating in real time is a strong judge moment
- Judges who know graph databases will recognise it immediately

**Cons:**
- If Docker fails mid-demo, the entire product is down
- 2–4 hrs setup time that should be spent on agent logic
- Cognee's Neo4j adapter has had occasional connection pool issues

### Trade-off analysis

Neo4j Browser is tempting purely for demo optics. The mitigation is a hybrid approach: use defaults throughout development, then on Day 6 attempt the Neo4j swap in a separate branch with a strict 2-hour time-box. If it breaks, revert to defaults. Use a pyvis HTML graph export for all demo visualisations regardless of backend — 10 lines of code, embeds in Streamlit via `st.components.v1.html()`.

### Consequences

- Default path: zero infra setup, demo runs on any laptop
- Neo4j path: add `COGNEE_GRAPH_BACKEND=neo4j` to `.env` and test on Day 6 in a branch
- pyvis graph export is implemented regardless of backend choice

### Action items

- [ ] Person 1 confirms LanceDB default works with `await cognee.cognify(["test"])` on Day 1
- [ ] Day 6 stretch: attempt Neo4j swap in a separate branch, 2-hour time-box maximum
- [ ] Add pyvis graph visualisation embedded in the Streamlit report page regardless of backend

---

## ADR-003: UI framework

**Status:** Proposed
**Date:** 2026-06-28
**Deciders:** Person 4 (UI lead)

### Context

The UI must: (a) let a recruiter upload a JD and resume, (b) run a live chat interview session with streaming responses, (c) display a structured post-interview report. It needs to be fully built in roughly 6–8 hours across Days 4–5.

### Decision

Use **Streamlit** with `st.chat_message`, `st.chat_input`, and `st.write_stream`.

### Options considered

#### Option A: Streamlit

| Dimension | Assessment |
|---|---|
| Setup time | 15 min |
| Streaming support | Native (`st.write_stream`) |
| File upload | Native (`st.file_uploader`) |
| Chat UI | Native (`st.chat_message`, `st.chat_input`) |
| Deployability | `streamlit run app.py` — zero config |

**Pros:**
- Chat interface looks professional out of the box
- Streaming LLM responses work natively since v1.28
- File upload with PDF support is two lines of code
- Entire UI can be a single `app.py` file
- Three-page flow maps cleanly to `st.session_state["page"]`

**Cons:**
- Single-threaded — concurrent users block each other (irrelevant for a demo)
- Limited layout control compared to React
- No real-time push from backend — requires `st.rerun()` polling

#### Option B: FastAPI + React / Next.js

| Dimension | Assessment |
|---|---|
| Setup time | 4–6 hrs minimum |
| Streaming support | SSE or WebSocket (must be implemented manually) |
| File upload | Manual multipart handling |
| Chat UI | Must be built from scratch or via a library |
| Deployability | Two separate processes, CORS configuration required |

**Pros:**
- Production-quality, fully customisable
- Impressive to judges who examine the code

**Cons:**
- 4–6 hr setup consumes almost the entire UI budget
- Streaming requires Server-Sent Events or WebSockets — non-trivial to wire correctly
- Over-engineered for a hackathon demo

#### Option C: Gradio

| Dimension | Assessment |
|---|---|
| Setup time | 10 min |
| Streaming support | Native |
| Chat UI | `gr.ChatInterface` — works well |
| Deployability | Single command |

**Pros:**
- Even simpler than Streamlit for pure chat interfaces

**Cons:**
- Less control over multi-page layout
- Streamlit's multi-page support is better for the upload → interview → report three-screen flow

### Trade-off analysis

Streamlit wins cleanly. The three-screen flow maps directly to Streamlit's `st.session_state` navigation pattern. Built-in chat components mean Person 4 can have a working prototype in 2 hours and use the remaining time on the report layout and pyvis integration.

### Consequences

- App has three logical pages managed via `st.session_state["page"]`: `"upload"`, `"interview"`, `"report"`
- Streaming: `st.write_stream(client.messages.stream(...))` handles interview turns
- Report page renders the analysis agent output using `st.metric`, `st.progress`, and `st.dataframe`
- pyvis graph HTML embedded via `st.components.v1.html(graph_html, height=400)`
- `forget()` button on the report page calls `cognee.forget(candidate_id)` — demonstrates full memory lifecycle

### Action items

- [ ] Person 4 scaffolds three-page Streamlit app with `st.session_state` navigation on Day 2 (target: 2 hrs)
- [ ] File upload → calls `session_start()` function (even if mocked) by end of Day 2
- [ ] Streaming interview turn working end-to-end by end of Day 4

---

## ADR-004: Cross-session memory strategy

**Status:** Proposed
**Date:** 2026-06-28
**Deciders:** Full team — this is a product decision, not just a tech decision

### Context

The hackathon theme is "give your AI a memory." The project's differentiation is that the Interviewer agent gets smarter across sessions. This ADR defines exactly what "smarter" means, because it determines what is stored, what is retrieved, and what is demonstrated to judges.

Two distinct flavours of cross-session memory are possible and they serve different parts of the demo story.

### Decision

Implement **both flavours** but prioritise Flavour 1 for the demo. Flavour 2 is a stretch goal for Day 5–6.

### Options considered

#### Option A — Flavour 1: Candidate memory (remembering a specific person)

The system recalls everything about a candidate across multiple interview rounds. On a second interview, the agent surfaces:

> "Last time Alice struggled with system design questions (2/5) but excelled at Python fundamentals (5/5). Probe system design deeper. Do not re-ask questions she already answered well."

`recall(candidate_id="alice_jones")` returns prior scores, gap flags, and unanswered questions.

| Dimension | Assessment |
|---|---|
| Cognee APIs used | `cognify`, `remember`, `recall`, `forget` |
| Demo clarity | Very high — judges immediately understand the value |
| Build effort | Medium — approximately 1 day |
| Data needed | 1–2 synthetic prior sessions for the demo candidate |

#### Option B — Flavour 2: Role memory (improving question quality over hires)

After interviewing several candidates for the same role, `memify()` builds a graph of which questions best differentiated strong from weak candidates. The next interview for that role uses this institutional knowledge.

`recall(role="senior_backend_engineer")` returns high-signal question templates with performance metadata.

| Dimension | Assessment |
|---|---|
| Cognee APIs used | `cognify`, `memify`, `recall` |
| Demo clarity | Medium — requires explanation |
| Build effort | Medium–High — synthetic history needed |
| Data needed | 3–5 synthetic past interviews per role |

### Trade-off analysis

Flavour 1 is the more visceral demo moment — showing that the AI "remembered" a specific person is immediately relatable and requires no explanation. Flavour 2 is the more intellectually interesting story (institutional learning) but needs more setup data and more explanation time during the demo.

**Build Flavour 1 first.** It is the core demo and a complete story on its own. Flavour 2 becomes a closing "wow" moment if working, or a "future roadmap" slide if not.

### Consequences

- `seed_memory.py` creates 2–3 synthetic sessions for a returning candidate — essential for reliable demos, takes ~30 min to write
- `forget(candidate_id)` button in the UI demonstrates the full Cognee lifecycle and signals GDPR awareness — judges notice this
- Flavour 2 requires a `role_memory` namespace in Cognee — scoped as a Day 5 stretch goal
- Pre-seeded data must be committed to the repo so any team member can reproduce the demo on a fresh machine

### Action items

- [ ] Person 1 writes `seed_memory.py` by end of Day 2 — this unblocks all integration testing
- [ ] Person 2 adds `recall()` call at session start and injects returned context into the interviewer system prompt by Day 3
- [ ] Person 3 adds the `forget(candidate_id)` call to the report view by Day 5
- [ ] Day 5–6 stretch: Person 1 implements `memify()` role-level graph; Person 2 wires it into question ranking

---

## ADR dependency order for the sprint

```
ADR-001 (SDK choice)        ← Agree Day 1 morning — everyone unblocks on this
         |
ADR-002 (storage backend)   ← Person 1, Day 1–2
         |
ADR-004 (memory strategy)   ← Person 1 + 2, Day 2–3 (seed_memory.py unlocks this)
         |
ADR-003 (UI framework)      ← Person 4, Day 2 onward (can mock APIs until Day 4)
```

The only real Day 1 blocker is confirming Cognee's default stack runs on all team machines and agreeing on the inter-agent state dict schema. Everything else proceeds in parallel after that.
