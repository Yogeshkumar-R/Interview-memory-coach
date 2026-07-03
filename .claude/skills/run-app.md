---
name: run-app
description: >
  Launch the Interview Memory Coach Streamlit app and verify it works. Use whenever
  the user asks to run the app, test the UI, check if something looks right in the
  browser, verify a page works end-to-end, or confirm a change didn't break anything.
  Also triggers for: "does this work", "open the app", "start streamlit", "test this".
---

# Run App — Interview Memory Coach

## Prerequisites check

Before starting, verify:

```powershell
# Check ANTHROPIC_API_KEY is set
$env:ANTHROPIC_API_KEY

# Check dependencies installed
pip show streamlit cognee anthropic PyMuPDF pyvis
```

If `app.py` doesn't exist yet, the UI scaffolding needs to be built first.

## Start the app

```powershell
streamlit run app.py
```

Opens at http://localhost:8501. If port 8501 is in use:

```powershell
streamlit run app.py --server.port 8502
```

## Test the golden path

Walk through this sequence every time you start the app:

1. **Upload page** — Enter candidate ID `alice_jones`, paste any JD text, upload a
   small PDF. Click "Start Interview". Verify you land on the interview page without
   an error.

2. **Interview page** — Type a short answer. Verify the streaming response appears
   character-by-character (not all at once). Verify the chat history accumulates
   correctly. Answer 2–3 questions.

3. **Report page** — Verify `st.metric`, `st.progress`, `st.dataframe` all render.
   Verify the pyvis graph appears (even if empty on first run). Click the
   "Forget candidate data" button and verify it returns to the upload page.

## Common issues

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: cognee` | `pip install cognee` |
| `ModuleNotFoundError: fitz` | `pip install PyMuPDF` |
| `asyncio.run()` errors in Streamlit | Wrap all async calls with `asyncio.run()`, never `await` at top level |
| Streaming shows all at once | Ensure generator yields str chunks, not a single string |
| pyvis graph blank | Check `cognee.recall()` returns node/edge data; stub it if Cognee not ready |
| App crashes on PDF upload | PyMuPDF needs `fitz.open(stream=bytes_io.read(), filetype="pdf")` |

## Seed demo data first

If testing the cross-session recall feature, seed synthetic data before running:

```powershell
python seed_memory.py
```

Then use `alice_jones` as the candidate ID to see prior context appear.
