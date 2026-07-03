# Hangover AI — Where's My Context? — Team Plan

**Hackathon:** The Hangover Part AI (WeMakeDevs × Cognee) · Jun 29 – Jul 5 2026
**Use case:** Interview Memory Coach (UC1)
**Team:** A, S, N, Y
**Remaining time:** Jul 1 – Jul 5 (4 build/submit days, today Jun 30 treated as setup-only and excluded)

**Judging criteria (confirmed from hackathon site):**
1. Depth of use of Cognee's memory lifecycle APIs (`cognify`, `remember`, `recall`, `memify`, `forget`) and the hybrid graph-vector layer
2. Polish / intuitiveness of the actual product experience
3. Clarity of demo, README, and submission write-up

---

## Jul 1 — Core loop wired

**A (Cognee lead)**
- Finish `seed_memory.py` — 2–3 synthetic prior interview sessions for a returning candidate
- Integrate `recall()`, test cross-session retrieval end to end
- Confirm `cognify()` entity graph (Candidate / Session / QAPair / Score) is stable

**S (Agents)**
- Build Interviewer agent: dialogue state, question generation
- Call `remember()` after every Q&A turn
- Wire `recall()` output into the interviewer's system prompt (candidate context injection)

**N (Analysis)**
- Build scoring logic: score each answer against JD requirements
- Flag skill gaps vs. resume claims

**Y (UI)**
- Wire file upload (JD + resume) to `session/start` (mock backend if needed)
- Build out the chat UI shell for the interview page

**End of day:** lock the inter-agent state dict schema if not already locked — this blocks everyone.

---

## Jul 2 — Streaming + analysis

**A**
- Validate graph integrity after multiple sessions / repeated `cognify()` calls
- Start `memify()` groundwork for role-level question quality (Flavour 2, stretch)

**S**
- Add follow-up probe logic, session continuity across turns
- Finalize streaming via `anthropic.messages.stream()`

**N**
- Build full Analysis agent: report dict `{ summary, scores[], gaps[], recommendation }`
- Call `memify()` after session end to update question-quality metadata

**Y**
- Wire `st.write_stream()` to the interviewer agent for live streaming chat — this is the core demo moment, prioritize it working smoothly over anything else today

---

## Jul 3 — End-to-end + lifecycle demo

**A**
- If time allows: `memify()` role graph (Flavour 2). If not, stop touching Cognee internals and lock Flavour 1 (candidate memory) as the demo story.

**S**
- Full end-to-end test: upload → interview → session end → report
- Fix breakages found during the run-through

**N**
- Polish report page output: `st.metric`, `st.progress`, `st.dataframe`

**Y**
- Embed pyvis graph visualization (`st.components.v1.html`) showing the live memory graph
- Add `forget(candidate_id)` button — judges specifically reward visible lifecycle completeness (remember/recall/memify/forget), don't skip this

**Note:** Do not attempt a Neo4j swap. ADR-002 already treats it as optional, it costs hours, and the demo-visibility need is already covered by pyvis. Skip it entirely given the compressed timeline.

---

## Jul 4 — Polish, demo script, submission prep

**All four**
- Bug bash: run the full demo flow 3+ times on a clean machine to catch environment/setup issues

**S + Y**
- Record a backup demo video — mandatory safety net in case the live demo breaks

**A**
- Write the "how we used Cognee" section of the submission. Be specific: which lifecycle calls (`cognify`, `remember`, `recall`, `memify`, `forget`) do what, and why — this is explicitly scored

**N**
- Write final README: problem, solution, demo link, architecture diagram

---

## Jul 5 — Submit

- Final run-through of the live demo
- Submit the project form
- Optional: blog post / social post if going for the swag tracks (Keychron keyboards for best blogs, swag for top social posts)

---

## Standing reminders

- Flavour 1 (candidate memory — "AI remembers a specific person") is the primary demo story. Flavour 2 (role memory via `memify()`) is a stretch goal only — don't let it block core flow.
- `forget(candidate_id)` must stay in the final build; it demonstrates full lifecycle awareness and is called out by judging criteria.
- No auth, no cloud infra — local-only, `streamlit run app.py` should be the entire deployment story.
