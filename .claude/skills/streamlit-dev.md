---
name: streamlit-dev
description: >
  Guide for building and editing the Interview Memory Coach Streamlit UI (app.py).
  Use this skill whenever the user mentions: adding a page, wiring upload, chat UI,
  streaming interviewer responses, report page, pyvis graph, forget button, or any
  st.* component in this project. Also trigger when the user says "build the UI",
  "wire the frontend", "add the Streamlit page", or asks how something should look
  in the app.
---

# Streamlit UI — Interview Memory Coach

## App structure

The entire UI lives in `app.py`. Navigation is driven by `st.session_state["page"]`
with three values: `"upload"`, `"interview"`, `"report"`.

```python
# Top of app.py — always initialise defaults before any st.* call
import streamlit as st
import asyncio

if "page" not in st.session_state:
    st.session_state["page"] = "upload"

page = st.session_state["page"]
if page == "upload":
    show_upload()
elif page == "interview":
    show_interview()
elif page == "report":
    show_report()
```

To navigate between pages, set the key and rerun:
```python
st.session_state["page"] = "interview"
st.rerun()
```

## Session state schema

Initialise all keys at startup so every page can safely read them:

```python
DEFAULTS = {
    "page": "upload",
    "session_id": None,
    "candidate_id": None,
    "jd_text": "",
    "resume_text": "",
    "extracted_entities": {},
    "questions": [],
    "qa_pairs": [],          # list of {"question": str, "answer": str, "score": int|None}
    "prior_context": None,
    "report": None,
    "messages": [],          # st.chat_message history for the interview page
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v
```

## Page: "upload"

Goal: collect JD text + resume PDF, call `session_start()`, then navigate to interview.

```python
def show_upload():
    st.title("Interview Memory Coach")
    st.subheader("Upload documents")

    candidate_id = st.text_input("Candidate ID", placeholder="e.g. alice_jones")
    jd_input = st.text_area("Job Description", height=200)
    resume_file = st.file_uploader("Resume (PDF)", type=["pdf"])

    if st.button("Start Interview", disabled=not (candidate_id and jd_input and resume_file)):
        with st.spinner("Analysing documents…"):
            import fitz  # PyMuPDF
            doc = fitz.open(stream=resume_file.read(), filetype="pdf")
            resume_text = "\n".join(p.get_text() for p in doc)

            result = asyncio.run(session_start(
                jd=jd_input,
                resume_text=resume_text,
                candidate_id=candidate_id,
            ))

        st.session_state.update({
            "session_id": result["session_id"],
            "candidate_id": candidate_id,
            "jd_text": jd_input,
            "resume_text": resume_text,
            "questions": result["questions"],
            "prior_context": result.get("prior_context"),
            "messages": [],
        })
        st.session_state["page"] = "interview"
        st.rerun()
```

## Page: "interview"

Goal: run the live streaming chat interview. Each turn calls `session_answer()` and
streams the response directly into the chat.

```python
def show_interview():
    st.title("Interview Session")

    if st.session_state["prior_context"]:
        st.info(f"Prior context loaded: {st.session_state['prior_context']}")

    # Render message history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Show first question if no messages yet
    if not st.session_state["messages"] and st.session_state["questions"]:
        first_q = st.session_state["questions"][0]
        st.session_state["messages"].append({"role": "assistant", "content": first_q})
        with st.chat_message("assistant"):
            st.markdown(first_q)

    # Candidate input
    if answer := st.chat_input("Your answer…"):
        st.session_state["messages"].append({"role": "user", "content": answer})
        with st.chat_message("user"):
            st.markdown(answer)

        # Stream the next question / follow-up
        with st.chat_message("assistant"):
            response_text = st.write_stream(
                stream_answer(
                    session_id=st.session_state["session_id"],
                    answer=answer,
                )
            )
        st.session_state["messages"].append({"role": "assistant", "content": response_text})

        if response_text.strip().lower().startswith("[end]"):
            if st.button("End interview & generate report"):
                _end_session()
```

### Streaming helper

`session_answer()` must return a generator that yields text chunks for `st.write_stream`:

```python
def stream_answer(session_id: str, answer: str):
    """Yield text chunks from the interviewer agent stream."""
    from agents.interviewer import get_next_question_stream
    for chunk in asyncio.run(get_next_question_stream(session_id, answer)):
        yield chunk
```

`st.write_stream()` accepts any iterable of strings — keep it simple.

## Page: "report"

Goal: show structured analysis output, pyvis memory graph, and forget button.

```python
def show_report():
    report = st.session_state["report"]
    if not report:
        st.warning("No report available.")
        return

    st.title("Interview Report")
    st.markdown(f"**Summary:** {report['summary']}")

    # Scores
    st.subheader("Scores")
    cols = st.columns(len(report["scores"]))
    for col, score in zip(cols, report["scores"]):
        col.metric(score["skill"], f"{score['value']}/5")

    # Gaps
    if report["gaps"]:
        st.subheader("Skill gaps")
        gap_data = [{"Skill": g["skill"], "Gap": g["description"]} for g in report["gaps"]]
        st.dataframe(gap_data, use_container_width=True)

    # Recommendation
    st.subheader("Recommendation")
    st.progress(report["recommendation_score"] / 100)
    st.markdown(report["recommendation"])

    # Memory graph
    st.subheader("Memory graph")
    graph_html = build_memory_graph_html(st.session_state["session_id"])
    st.components.v1.html(graph_html, height=400, scrolling=False)

    # Forget button — demonstrates full Cognee lifecycle (required for submission)
    st.divider()
    if st.button("Forget candidate data (GDPR)", type="secondary"):
        import cognee, asyncio
        asyncio.run(cognee.forget(st.session_state["candidate_id"]))
        st.success("Candidate data removed from memory.")
        st.session_state["page"] = "upload"
        st.rerun()
```

## pyvis graph helper

Build the graph from Cognee and return an HTML string for `st.components.v1.html`:

```python
def build_memory_graph_html(session_id: str) -> str:
    from pyvis.network import Network
    import cognee, asyncio

    graph_data = asyncio.run(cognee.recall(session_id))  # adjust to actual API
    net = Network(height="390px", width="100%", bgcolor="#0e1117", font_color="white")

    for node in graph_data.get("nodes", []):
        net.add_node(node["id"], label=node["label"], color=node.get("color", "#4a9eff"))
    for edge in graph_data.get("edges", []):
        net.add_edge(edge["source"], edge["target"], title=edge.get("label", ""))

    net.set_options("""{"physics": {"enabled": true}}""")
    return net.generate_html()
```

## Cognee config (top of app.py)

```python
import cognee
cognee.config.set_llm_provider("anthropic")
# cognee uses ANTHROPIC_API_KEY from the environment automatically
```

## Async in Streamlit

Streamlit is single-threaded. Wrap every `async` call with `asyncio.run()`.
Never use `await` at the top level of a Streamlit script.

```python
result = asyncio.run(some_async_agent_function(...))
```

## Key constraints

- `forget()` button on the report page is **mandatory** — do not remove it.
- `st.write_stream()` requires an iterable of strings, not a coroutine.
- Keep all navigation via `st.session_state["page"]` + `st.rerun()` — no `st.switch_page`.
- PDF parsing uses PyMuPDF (`import fitz`), not pdfplumber.
