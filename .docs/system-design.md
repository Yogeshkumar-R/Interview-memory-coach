# System design — Interview Memory Coach (UC1)

**Hackathon:** WeMakeDevs × Cognee · Jun 29 – Jul 5 2026
**Team size:** 4 · **Available time:** ~25 hrs total

---

## 1. Requirements

### Functional (hackathon scope)

- Recruiter uploads a Job Description (JD) and candidate resume
- System auto-generates targeted interview questions from JD↔resume gap analysis
- Agent conducts a text interview session with streaming responses
- Every Q&A pair is stored in Cognee via `cognify()` + `remember()`
- Cross-session: `recall()` surfaces prior performance for returning candidates
- Post-interview analysis agent generates a structured report (scores, gaps, recommendation)
- `memify()` improves question quality across accumulated interviews
- `forget(candidate_id)` clears candidate data (GDPR demonstration)

### Non-functional (hackathon reality)

| Concern | Target |
|---|---|
| Latency | < 5s per question generation |
| Reliability | Single-user demo must not crash |
| Auth | None required (single-tenant, local) |
| Deployment | `streamlit run app.py` — zero config |

### Constraints

- Python-fluent team
- Cognee required and must use memory lifecycle APIs deeply
- No cloud infra — everything runs locally on a laptop

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────┐
│                        UI layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Recruiter UI │  │ Candidate UI │  │ Report viewer│  │
│  │ Upload JD +  │  │ Chat session │  │ Post-         │  │
│  │ resume       │  │ streaming    │  │ interview     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼─────────────────┼─────────────────┼───────────┘
          │                 │                 │
┌─────────▼─────────────────▼─────────────────▼───────────┐
│                      Agent layer                         │
│         (Python · raw Anthropic SDK · async)             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ Intake      │  │ Interviewer  │  │ Analysis      │   │
│  │ agent       │  │ agent        │  │ agent         │   │
│  │ Parse JD,   │  │ Q generation │  │ Score, gap    │   │
│  │ resume      │  │ + dialogue   │  │ analysis      │   │
│  └─────────────┘  └──────────────┘  └───────────────┘   │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                  Cognee memory layer                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ cognify()   │  │ recall()     │  │ memify()      │   │
│  │ Ingest      │  │ Prior session│  │ Improve across│   │
│  │ session     │  │ context      │  │ hires         │   │
│  └─────────────┘  └──────────────┘  └───────────────┘   │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                       Storage                            │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ Graph store │  │ Vector store │  │ File store    │   │
│  │ NetworkX    │  │ LanceDB      │  │ Local disk    │   │
│  │ Entity      │  │ Semantic     │  │ Resumes,      │   │
│  │ relations   │  │ search       │  │ reports       │   │
│  └─────────────┘  └──────────────┘  └───────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Component descriptions

### Intake agent

Receives the JD and resume PDF, extracts structured text, identifies key entities (required skills, experience levels, role expectations), and calls `cognify()` to build the initial entity graph for the session.

**Inputs:** JD string, resume PDF (base64)
**Outputs:** `session_id`, extracted entities dict, initial question set

### Interviewer agent

Maintains the dialogue state, generates follow-up questions based on candidate answers, and stores each Q&A pair live via `remember()`. On session start it calls `recall(candidate_id)` to load any prior session context and adjusts question depth accordingly.

**Inputs:** `session_id`, candidate answer string
**Outputs:** next question string (streamed), optional follow-up probe

### Analysis agent

Runs post-session. Reads the full session graph from Cognee, scores each answer against the JD requirements, identifies skill gaps vs. resume claims, and writes a structured report. Calls `memify()` to update role-level question quality metadata.

**Inputs:** `session_id`
**Outputs:** report dict `{ summary, scores[], gaps[], recommendation }`

---

## 4. API contracts

Three endpoints exposed by a thin FastAPI layer (or called directly from Streamlit):

```python
POST /session/start
  body:    { jd: str, resume_pdf: str (base64), candidate_id: str }
  returns: { session_id: str, questions: list[str], prior_context: dict | None }

POST /session/answer
  body:    { session_id: str, question_index: int, answer: str }
  returns: { next_question: str | None, follow_up: str | None }

POST /session/end
  body:    { session_id: str }
  returns: { report: { summary: str, scores: list, gaps: list, recommendation: str } }
```

Inter-agent state is passed as plain Python dicts. No message queues needed at hackathon scale.

---

## 5. Cognee memory data model

Each `cognify()` call builds a graph with these entities and edges:

```
Candidate ──has_skill──────────> Skill
Candidate ──applied_for────────> Role
Role      ──requires_skill─────> Skill
Session   ──belongs_to─────────> Candidate
Session   ──contains───────────> QAPair
QAPair    ──assessed_by────────> Score
Score     ──flags──────────────> Skill  (gap or strength)
```

`memify()` adds a second graph layer:

```
QuestionTemplate ──performed_well_on──> Role
QuestionTemplate ──discriminated──────> Skill
```

This is how question quality improves across hires — the Interviewer agent `recall()`s high-signal question templates when generating questions for a new role match.

---

## 6. Cross-session memory strategy

Two flavours are implemented; Flavour 1 is the primary demo story.

**Flavour 1 — Candidate memory (demo centrepiece)**

`recall(candidate_id)` returns prior scores, unanswered questions, and flagged gaps. On the candidate's second interview session, the agent surfaces this context directly in its system prompt:

```
"Last session: Alice struggled with system design (score 2/5) but
excelled at Python fundamentals (5/5). Probe system design deeper
this session. Do not re-ask questions already answered well."
```

**Flavour 2 — Role memory (stretch goal, Day 5–6)**

After several interviews for the same role, `memify()` builds a quality graph across `QuestionTemplate` nodes. The Interviewer agent uses this to rank question candidates by historical discrimination power before presenting them.

**Seeding for the demo:** Run `seed_memory.py` before the demo to pre-load 2–3 synthetic prior sessions. This ensures `recall()` returns meaningful context on Day 1 of the demo even with no real users.

---

## 7. Tech stack

| Layer | Choice | Rationale |
|---|---|---|
| UI | Streamlit | Chat components, file upload, streaming — all native |
| Agent orchestration | Raw Anthropic SDK | Transparent, debuggable, no abstraction fighting Cognee |
| Memory | Cognee (self-hosted) | Required; `cognee.config.set_llm_provider("anthropic")` |
| Vector store | LanceDB (Cognee default) | Zero setup, embedded, persists to `~/.cognee/` |
| Graph store | NetworkX (Cognee default) | No Docker needed; exportable to pyvis for demo |
| PDF parsing | PyMuPDF (`fitz`) | 3 lines, fast, no external process |
| Graph visualisation | pyvis → `st.components.v1.html` | Shows live memory graph to judges |
| Voice (optional) | OpenAI Whisper | Bolt on Day 5 only if core is done |

---

## 8. Day-by-day build plan

| Day | Person 1 (Cognee) | Person 2 (Agents) | Person 3 (Analysis) | Person 4 (UI) |
|---|---|---|---|---|
| 1 | Cognee setup, `cognify` smoke test | `agents/base.py`, SDK client, retry wrapper | — | Streamlit 3-page scaffold |
| 2 | Entity graph design, `seed_memory.py` | Intake agent + question generation | Analysis agent skeleton | File upload → session start wired |
| 3 | `recall()` integration, cross-session test | Interviewer agent, `remember()` per turn | Scoring logic | Streaming chat interview working |
| 4 | `memify()` role graph (Flavour 2 start) | Session continuity, follow-up probes | Report dict structure | Report page layout |
| 5 | Neo4j swap attempt (2-hr time-box) | End-to-end session test | Report polish | pyvis graph embed, `forget()` button |
| 6 | Buffer / polish | Buffer / polish | Buffer / polish | Demo script, video recording |
| 7 | Submission writeup | — | — | — |

---

## 9. Day 1 validation script

Run this first. If it completes without errors, the foundation is solid.

```python
import asyncio
import cognee
import anthropic
import fitz  # PyMuPDF

async def smoke_test():
    # 1. Parse a resume
    doc = fitz.open("sample_resume.pdf")
    resume_text = "\n".join(p.get_text() for p in doc)

    # 2. Ingest into Cognee
    jd_text = "Senior Backend Engineer: Python, system design, distributed systems"
    await cognee.cognify([resume_text, jd_text])

    # 3. Recall (empty first run — should return None or empty)
    context = await cognee.recall("candidate_001")
    print("Prior context:", context)

    # 4. Generate questions using Claude
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Context: {context}\nJD: {jd_text}\nResume: {resume_text[:500]}\n\nGenerate 5 targeted interview questions."
        }]
    )
    print(msg.content[0].text)

asyncio.run(smoke_test())
```

---

## 10. Trade-offs

**Streamlit single-thread:** `st.write_stream()` with `anthropic.messages.stream()` handles streaming natively since Streamlit 1.28. No workaround needed.

**NetworkX vs Neo4j:** Defaults work on any laptop without Docker. If Neo4j Browser demo visuals are wanted, attempt the swap on Day 5 in a branch with a 2-hour time-box. Revert if unstable. Use pyvis regardless for graph visualisation in the UI.

**No auth / multi-tenancy:** Intentional for hackathon scope. The `forget(candidate_id)` button demonstrates awareness of the gap and covers GDPR intent. Call it out explicitly in the submission.

**`memify()` cold start:** Without real usage history, Flavour 2 (role memory) shows nothing interesting. Mitigation is `seed_memory.py` with synthetic interviews. Even 3 seeded sessions produce a visible graph that demonstrates the concept.
