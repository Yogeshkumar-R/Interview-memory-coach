# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Interview Memory Coach** — a hackathon submission (WeMakeDevs × Cognee, Jun 29–Jul 5 2026). An AI-powered interview system that remembers candidates across sessions using Cognee's memory lifecycle APIs. The entire app runs locally with `streamlit run app.py`.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Seed synthetic memory data (run before demo)
python seed_memory.py

# Run the main app (FastAPI + full chat UI with voice)
uvicorn server:app --reload --port 8000
# then open http://localhost:8000

# Run the legacy Streamlit app (backup)
streamlit run app.py

# Run the Day 1 smoke test to verify Cognee + Groq integration
python smoke_test.py
```

## Architecture

Three-layer stack: FastAPI + HTML/JS UI → Python agents (Groq SDK) → Cognee memory.

```
UI (app.py)
  └─ page: "upload"     → calls session_start()   → Intake agent
  └─ page: "interview"  → calls session_answer()  → Interviewer agent  
  └─ page: "report"     → calls session_end()     → Analysis agent
                                                        │
                                              Cognee memory layer
                                   (NetworkX graph + LanceDB vector, ~/.cognee/)
```

### Agents (`agents/`)

| File | Responsibility |
|---|---|
| `agents/base.py` | Shared Anthropic client, ~20-line retry wrapper, streaming helper |
| `agents/intake.py` | Parse JD + resume PDF via PyMuPDF, call `cognee.cognify()`, return initial question set |
| `agents/interviewer.py` | Dialogue state, question generation, `remember()` per turn, `recall()` at session start |
| `agents/analysis.py` | Post-session scoring, gap analysis, `memify()` for role-level quality metadata |

Every agent is an `async def` function accepting a `messages: list` parameter. State between agents is a plain dict — schema must be agreed before writing any agent.

### Inter-agent state dict schema

```python
{
    "session_id": str,
    "candidate_id": str,
    "jd_text": str,
    "resume_text": str,
    "extracted_entities": dict,   # set by Intake agent
    "questions": list[str],       # set by Intake agent
    "qa_pairs": list[dict],       # appended by Interviewer agent per turn
    "prior_context": dict | None, # set by recall() at session start
    "report": dict | None,        # set by Analysis agent
}
```

### Cognee memory data model

```
Candidate ──has_skill──────────> Skill
Candidate ──applied_for────────> Role
Role      ──requires_skill─────> Skill
Session   ──belongs_to─────────> Candidate
Session   ──contains───────────> QAPair
QAPair    ──assessed_by────────> Score
Score     ──flags──────────────> Skill  (gap or strength)
```

`memify()` adds a second layer: `QuestionTemplate ──performed_well_on──> Role`

### UI pages (`app.py`)

Three pages managed via `st.session_state["page"]`:
- `"upload"` — `st.file_uploader` for JD + resume PDF
- `"interview"` — `st.chat_message` / `st.chat_input` with `st.write_stream()` for streaming
- `"report"` — `st.metric`, `st.progress`, `st.dataframe` for analysis output + pyvis graph embed + `forget()` button

### Cognee lifecycle calls

| Call | Where | Purpose |
|---|---|---|
| `cognify()` | Intake agent | Build entity graph from JD + resume |
| `remember()` | Interviewer agent, every turn | Store each Q&A pair live |
| `recall(candidate_id)` | Interviewer agent, session start | Surface prior performance |
| `memify()` | Analysis agent, session end | Update role-level question quality graph |
| `forget(candidate_id)` | Report page UI button | GDPR demo — must stay in final build |

## Key decisions (from ADRs)

- **Raw Anthropic SDK only** — no LangChain/LlamaIndex. Cognee has no LangChain memory adapter; fighting it wastes hours.
- **Cognee defaults** — NetworkX + LanceDB. No Docker, no credentials. Neo4j swap is explicitly ruled out (ADR-002); use pyvis for graph visualisation instead.
- **Streamlit** — `st.write_stream()` + `anthropic.messages.stream()` handle streaming natively since v1.28.
- **`forget()` is mandatory** — judges score on full lifecycle visibility; do not remove it.
- **Flavour 1 (candidate memory) is the demo story** — Flavour 2 (role memory via `memify()`) is stretch only.

## Demo dependencies

- `seed_memory.py` must be committed and reproducible on any team machine — it pre-loads 2–3 synthetic sessions so `recall()` returns meaningful context even with no real users.
- `GROQ_API_KEY` must be set in the environment (`.env` file, not committed).
- Cognee config: configured via `agents/memory._cognee_config()` to use Groq (OpenAI-compatible endpoint).

## Submission checklist (Jul 5)

- [ ] Full demo flow runs 3+ times on a clean machine without crashing
- [ ] `forget(candidate_id)` button visible and functional
- [ ] All five Cognee lifecycle APIs used: `cognify`, `remember`, `recall`, `memify`, `forget`
- [ ] Backup demo video recorded
- [ ] README written with architecture diagram
- [ ] Submission writeup explains specifically what each Cognee lifecycle call does (this is scored)
