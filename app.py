import streamlit as st
import asyncio
import time
import uuid
from typing import Generator

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Page config must be the first Streamlit call ──────────────────────────────
st.set_page_config(
    page_title="Interview Memory Coach",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
def _inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

    .stApp {
        background-color: #080d1a;
        background-image:
            radial-gradient(ellipse at 15% 55%, rgba(0,212,255,0.045) 0%, transparent 52%),
            radial-gradient(ellipse at 85% 15%, rgba(100,40,220,0.04) 0%, transparent 45%),
            url("data:image/svg+xml,%3Csvg width='52' height='52' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='26' cy='26' r='0.75' fill='rgba(0,180,255,0.13)'/%3E%3C/svg%3E");
    }

    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 2rem; max-width: 1120px; }

    /* ── Inputs ── */
    .stTextInput input, .stTextArea textarea {
        background: rgba(255,255,255,0.035) !important;
        border: 1px solid rgba(0,212,255,0.18) !important;
        border-radius: 7px !important;
        color: #e2e8f0 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.9rem !important;
        transition: border-color .2s, box-shadow .2s !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: rgba(0,212,255,0.55) !important;
        box-shadow: 0 0 0 3px rgba(0,212,255,0.08) !important;
        outline: none !important;
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #334155 !important;
    }

    /* ── Labels ── */
    .stTextInput label, .stTextArea label, .stFileUploader label,
    [data-testid="stFileUploaderDropzone"] {
        color: #475569 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.7rem !important;
        letter-spacing: 0.09em !important;
        text-transform: uppercase !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #00d4ff 0%, #0091b5 100%) !important;
        color: #080d1a !important;
        border: none !important;
        border-radius: 7px !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        letter-spacing: 0.06em !important;
        padding: 0.55rem 1.4rem !important;
        transition: transform .18s, box-shadow .18s !important;
    }
    .stButton > button:hover:not(:disabled) {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 24px rgba(0,212,255,0.28) !important;
    }
    .stButton > button:disabled {
        opacity: 0.35 !important;
        cursor: not-allowed !important;
    }
    .stButton > button[kind="secondary"] {
        background: transparent !important;
        border: 1px solid rgba(239,68,68,0.4) !important;
        color: #f87171 !important;
    }
    .stButton > button[kind="secondary"]:hover:not(:disabled) {
        border-color: rgba(239,68,68,0.75) !important;
        box-shadow: 0 6px 24px rgba(239,68,68,0.18) !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploaderDropzone"] {
        border: 1px dashed rgba(0,212,255,0.22) !important;
        border-radius: 8px !important;
        background: rgba(0,212,255,0.02) !important;
        padding: 1rem !important;
    }

    /* ── Chat ── */
    [data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.025) !important;
        border: 1px solid rgba(255,255,255,0.055) !important;
        border-radius: 9px !important;
        margin-bottom: 0.65rem !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background: rgba(0,212,255,0.035) !important;
        border-color: rgba(0,212,255,0.1) !important;
    }
    .stChatInput textarea {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(0,212,255,0.2) !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
    }

    /* ── Metrics ── */
    [data-testid="metric-container"] {
        background: rgba(255,255,255,0.025) !important;
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 9px !important;
        padding: 1.1rem 1rem !important;
    }
    [data-testid="stMetricValue"] {
        color: #00d4ff !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1.6rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: #475569 !important;
        font-size: 0.68rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.09em !important;
        font-family: 'IBM Plex Mono', monospace !important;
    }
    [data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

    /* ── Progress ── */
    [data-testid="stProgress"] > div { background: rgba(255,255,255,0.07) !important; border-radius: 4px !important; }
    [data-testid="stProgress"] > div > div {
        background: linear-gradient(90deg, #00d4ff, #0091b5) !important;
        border-radius: 4px !important;
        transition: width .5s ease !important;
    }

    /* ── Dataframe ── */
    .stDataFrame { border: 1px solid rgba(255,255,255,0.07) !important; border-radius: 9px !important; overflow: hidden !important; }
    .stDataFrame th { background: rgba(0,212,255,0.08) !important; color: #64748b !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.72rem !important; }
    .stDataFrame td { color: #94a3b8 !important; font-size: 0.82rem !important; }

    /* ── Alert / info ── */
    [data-testid="stAlert"] {
        border-radius: 8px !important;
        border-left: 3px solid #00d4ff !important;
        background: rgba(0,212,255,0.055) !important;
    }
    [data-testid="stAlert"] p { color: #94a3b8 !important; }

    /* ── Misc ── */
    .stSpinner > div { border-top-color: #00d4ff !important; }
    hr { border-color: rgba(255,255,255,0.07) !important; margin: 1.5rem 0 !important; }
    h1, h2, h3 { color: #e2e8f0 !important; }
    p, li { color: #94a3b8 !important; }
    code { color: #00d4ff !important; background: rgba(0,212,255,0.08) !important; }
    </style>
    """, unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS = {
    "page": "upload",
    "session_id": None,
    "candidate_id": None,
    "jd_text": "",
    "resume_text": "",
    "extracted_entities": {},
    "questions": [],
    "qa_pairs": [],
    "prior_context": None,
    "report": None,
    "messages": [],
    "interview_ended": False,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Shared header ─────────────────────────────────────────────────────────────
def _header(active: str):
    steps = [("upload", "01 · INTAKE"), ("interview", "02 · INTERVIEW"), ("report", "03 · REPORT")]
    badges = "".join(
        f'<span style="font-family:IBM Plex Mono,monospace;font-size:0.68rem;'
        f'color:{"#00d4ff" if s == active else "#2d3748"};'
        f'background:{"rgba(0,212,255,0.1)" if s == active else "transparent"};'
        f'border:1px solid {"rgba(0,212,255,0.3)" if s == active else "transparent"};'
        f'padding:0.22rem 0.8rem;border-radius:20px;transition:all .2s;">'
        f'{label}</span>'
        for s, label in steps
    )
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding-bottom:1.4rem;border-bottom:1px solid rgba(255,255,255,0.07);
                margin-bottom:2rem;">
        <span style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                     color:#00d4ff;letter-spacing:0.18em;">◈ MEMORY COACH</span>
        <div style="display:flex;gap:0.4rem;align-items:center;">{badges}</div>
    </div>
    """, unsafe_allow_html=True)


# ── Real backends ─────────────────────────────────────────────────────────────
import agents.intake as _intake
import agents.interviewer as _interviewer
import agents.analysis as _analysis
from agents.memory import forget_candidate as _forget


async def _session_start(jd: str, resume_text: str, candidate_id: str) -> dict:
    state = {
        **_DEFAULTS,
        "session_id":   f"sess_{str(uuid.uuid4())[:6].upper()}",
        "candidate_id": candidate_id,
        "jd_text":      jd,
        "resume_text":  resume_text,
    }
    return await _intake.run(state)


async def _session_end(state: dict) -> dict:
    return await _analysis.run(state)


def _stream_response(state: dict, answer: str, question_idx: int):
    """Sync generator for st.write_stream — delegates to interviewer agent."""
    yield from _interviewer.stream_response(state, answer, question_idx)


def _build_memory_graph(session_id: str, candidate_id: str) -> str:
    from pyvis.network import Network
    net = Network(height="380px", width="100%", bgcolor="#080d1a", font_color="#94a3b8")
    net.set_options("""{
      "nodes": {"font": {"size": 11}, "borderWidth": 1, "shape": "dot"},
      "edges": {"smooth": {"type": "continuous"}, "font": {"size": 9, "align": "middle"}, "color": {"color": "rgba(100,116,139,0.5)"}},
      "physics": {"stabilization": {"iterations": 180}}
    }""")

    _nodes = [
        (candidate_id,           "Candidate",              "#00d4ff", 22),
        ("senior_backend",       "Role: Senior Backend",   "#7c3aed", 18),
        ("skill_python",         "Python",                 "#10b981", 14),
        ("skill_sysdesign",      "System Design",          "#f59e0b", 14),
        ("skill_distributed",    "Distributed Systems",    "#f59e0b", 14),
        ("skill_comms",          "Communication",          "#10b981", 14),
        (session_id,             f"Session {session_id}",  "#334155", 16),
        ("qa_1",                 "Q&A: Systems at scale",  "#1e293b", 11),
        ("qa_2",                 "Q&A: Trade-offs",        "#1e293b", 11),
        ("qa_3",                 "Q&A: Debugging",         "#1e293b", 11),
        ("score_python",         "Score 5/5",              "#10b981", 12),
        ("score_sysdesign",      "Score 3/5",              "#f59e0b", 12),
        ("score_distributed",    "Score 2/5",              "#ef4444", 12),
    ]
    for nid, label, color, size in _nodes:
        net.add_node(nid, label=label, color=color, size=size)

    _edges = [
        (candidate_id,       "skill_python",      "has_skill"),
        (candidate_id,       "skill_sysdesign",   "has_skill"),
        (candidate_id,       "skill_comms",       "has_skill"),
        (candidate_id,       "senior_backend",    "applied_for"),
        ("senior_backend",   "skill_python",      "requires_skill"),
        ("senior_backend",   "skill_sysdesign",   "requires_skill"),
        ("senior_backend",   "skill_distributed", "requires_skill"),
        (session_id,         candidate_id,        "belongs_to"),
        (session_id,         "qa_1",              "contains"),
        (session_id,         "qa_2",              "contains"),
        (session_id,         "qa_3",              "contains"),
        ("qa_1",             "score_sysdesign",   "assessed_by"),
        ("qa_2",             "score_python",      "assessed_by"),
        ("qa_3",             "score_distributed", "assessed_by"),
        ("score_sysdesign",  "skill_sysdesign",   "flags_gap"),
        ("score_distributed","skill_distributed", "flags_gap"),
    ]
    for src, dst, label in _edges:
        net.add_edge(src, dst, title=label, label=label)

    return net.generate_html(notebook=False)


# ── Page: Upload ──────────────────────────────────────────────────────────────
def _page_upload():
    _header("upload")

    col_left, col_right = st.columns([1.15, 1], gap="large")

    with col_left:
        st.markdown("""
        <h1 style="font-family:'IBM Plex Mono',monospace;font-size:2.1rem;
                   font-weight:600;color:#e2e8f0;line-height:1.15;margin-bottom:0.3rem;">
            Candidate<br/><span style="color:#00d4ff;">Intake</span>
        </h1>
        <p style="color:#475569;font-size:0.88rem;margin-bottom:1.8rem;">
            Upload the job description and resume to begin a<br/>
            memory-aware interview session.
        </p>
        """, unsafe_allow_html=True)

        candidate_id = st.text_input("Candidate ID", placeholder="e.g. alice_jones",
                                     help="Used to retrieve prior session memory via Cognee recall()")
        jd_text = st.text_area("Job Description", height=230,
                               placeholder="Paste the full job description here…")

    with col_right:
        st.markdown("<div style='height:6rem'></div>", unsafe_allow_html=True)
        resume_file = st.file_uploader("Resume PDF", type=["pdf"])

        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

        # Memory status indicator
        _cid = candidate_id.strip().lower().replace(" ", "_") if candidate_id else ""
        if _cid in ("alice_jones", "alice"):
            st.markdown("""
            <div style="border:1px solid rgba(0,212,255,0.35);border-radius:9px;
                        padding:0.9rem 1.1rem;background:rgba(0,212,255,0.06);">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;
                             color:#00d4ff;text-transform:uppercase;letter-spacing:0.12em;">
                    ◈ Prior memory detected
                </span><br/>
                <span style="font-size:0.8rem;color:#64748b;margin-top:0.3rem;display:block;">
                    1 session on record · Jun 15 2026
                </span>
            </div>
            """, unsafe_allow_html=True)
        elif candidate_id:
            st.markdown("""
            <div style="border:1px solid rgba(255,255,255,0.08);border-radius:9px;
                        padding:0.9rem 1.1rem;background:rgba(255,255,255,0.02);">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;
                             color:#334155;text-transform:uppercase;letter-spacing:0.12em;">
                    ○ First session — no prior memory
                </span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

        can_start = bool(candidate_id and jd_text and resume_file)

        if st.button("Start Interview  →", disabled=not can_start, use_container_width=True):
            with st.spinner("Parsing documents and initialising memory graph…"):
                try:
                    import fitz
                    doc = fitz.open(stream=resume_file.read(), filetype="pdf")
                    resume_text = "\n".join(p.get_text() for p in doc)
                except Exception:
                    resume_text = f"[Could not parse PDF: {resume_file.name}]"

                result = asyncio.run(_session_start(jd_text, resume_text, candidate_id))

            st.session_state.update({
                "session_id":    result["session_id"],
                "candidate_id":  candidate_id.strip(),
                "jd_text":       jd_text,
                "resume_text":   resume_text,
                "questions":     result["questions"],
                "prior_context": result.get("prior_context"),
                "messages":      [],
                "qa_pairs":      [],
                "interview_ended": False,
                "report":        None,
            })
            st.session_state["page"] = "interview"
            st.rerun()

        if not can_start and candidate_id:
            missing = []
            if not jd_text:    missing.append("job description")
            if not resume_file: missing.append("resume PDF")
            st.markdown(
                f"<p style='color:#334155;font-size:0.78rem;margin-top:0.5rem;'>"
                f"Missing: {', '.join(missing)}</p>",
                unsafe_allow_html=True,
            )


# ── Page: Interview ───────────────────────────────────────────────────────────
def _page_interview():
    _header("interview")

    col_chat, col_side = st.columns([2.2, 1], gap="large")

    with col_chat:
        st.markdown(f"""
        <div style="margin-bottom:1.4rem;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;
                         color:#334155;letter-spacing:0.1em;text-transform:uppercase;">
                Session · {st.session_state['session_id']}
            </span>
            <h2 style="font-size:1.45rem;color:#e2e8f0;margin:0.2rem 0 0;font-weight:500;">
                {st.session_state['candidate_id']}
            </h2>
        </div>
        """, unsafe_allow_html=True)

        # Prior context banner
        ctx = st.session_state["prior_context"]
        if ctx:
            st.markdown(f"""
            <div style="border:1px solid rgba(0,212,255,0.32);border-radius:9px;
                        padding:0.9rem 1.15rem;background:rgba(0,212,255,0.05);
                        margin-bottom:1.2rem;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;
                             color:#00d4ff;letter-spacing:0.1em;">
                    ◈ MEMORY ACTIVE · {ctx.get('session_date', 'prior session')}
                </span><br/>
                <span style="font-size:0.82rem;color:#64748b;margin-top:0.3rem;display:block;
                             line-height:1.5;">
                    {ctx.get('note', 'Prior session context loaded.')}
                </span>
            </div>
            """, unsafe_allow_html=True)

        # Render existing messages
        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Seed first question if fresh session
        if not st.session_state["messages"] and st.session_state["questions"]:
            first_q = st.session_state["questions"][0]
            st.session_state["messages"].append({"role": "assistant", "content": first_q})
            with st.chat_message("assistant"):
                st.markdown(first_q)

        # Ended state
        if st.session_state["interview_ended"]:
            st.markdown("""
            <div style="text-align:center;padding:1.5rem;border:1px dashed rgba(0,212,255,0.15);
                        border-radius:9px;margin-top:1rem;">
                <span style="font-family:'IBM Plex Mono',monospace;color:#334155;font-size:0.78rem;">
                    Interview concluded · Click "Generate Report" to continue
                </span>
            </div>
            """, unsafe_allow_html=True)
        else:
            if answer := st.chat_input("Type your answer…"):
                st.session_state["messages"].append({"role": "user", "content": answer})
                with st.chat_message("user"):
                    st.markdown(answer)

                answered_count = sum(1 for m in st.session_state["messages"] if m["role"] == "user")
                total_q = len(st.session_state["questions"])

                current_q = st.session_state["questions"][answered_count - 1]

                if answered_count >= total_q:
                    closing = (
                        "That covers everything I wanted to explore today. "
                        "Thank you — your responses give us a strong signal. "
                        "Click **Generate Report** in the sidebar to see the analysis."
                    )
                    with st.chat_message("assistant"):
                        st.markdown(closing)
                    st.session_state["messages"].append({"role": "assistant", "content": closing})
                    st.session_state["interview_ended"] = True
                else:
                    next_q = st.session_state["questions"][answered_count]
                    with st.chat_message("assistant"):
                        streamed = st.write_stream(
                            _stream_response(dict(st.session_state), answer, answered_count - 1)
                        )
                        follow = f"\n\n---\n\n**{next_q}**"
                        st.markdown(follow)
                    st.session_state["messages"].append(
                        {"role": "assistant", "content": streamed + follow}
                    )

                # remember() — store Q&A in Cognee after every turn
                asyncio.run(_interviewer.remember_turn(
                    candidate_id=st.session_state["candidate_id"],
                    session_id=st.session_state["session_id"],
                    question=current_q,
                    answer=answer,
                ))
                st.session_state["qa_pairs"].append(
                    {"question": current_q, "answer": answer}
                )

    # ── Sidebar panel ──────────────────────────────────────────────────────────
    with col_side:
        st.markdown("<div style='height:4rem'></div>", unsafe_allow_html=True)

        answered = sum(1 for m in st.session_state["messages"] if m["role"] == "user")
        total_q  = len(st.session_state["questions"])

        st.markdown(f"""
        <div style="border:1px solid rgba(255,255,255,0.07);border-radius:10px;
                    padding:1.3rem;background:rgba(255,255,255,0.02);">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                         color:#334155;text-transform:uppercase;letter-spacing:0.12em;">
                Progress
            </span>
            <div style="display:flex;justify-content:space-between;margin:0.7rem 0 0.4rem;">
                <span style="font-size:0.82rem;color:#64748b;">Questions answered</span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.82rem;
                             color:#00d4ff;">{answered}/{total_q}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.progress(min(answered / max(total_q, 1), 1.0))

        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

        # Question checklist
        st.markdown("""
        <div style="border:1px solid rgba(255,255,255,0.07);border-radius:10px;
                    padding:1.3rem;background:rgba(255,255,255,0.02);">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                         color:#334155;text-transform:uppercase;letter-spacing:0.12em;">
                Questions
            </span>
        """, unsafe_allow_html=True)

        for i, q in enumerate(st.session_state["questions"]):
            done   = i < answered
            color  = "#10b981" if done else "#1e293b"
            symbol = "✓" if done else f"0{i+1}"
            label_color = "#64748b" if done else "#2d3748"
            st.markdown(f"""
            <div style="display:flex;gap:0.55rem;align-items:flex-start;margin-top:0.6rem;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.62rem;
                             color:{color};min-width:1.4rem;padding-top:2px;">{symbol}</span>
                <span style="font-size:0.74rem;color:{label_color};line-height:1.4;">
                    {q[:60]}{'…' if len(q) > 60 else ''}
                </span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        if st.button("Generate Report  →", use_container_width=True, disabled=answered == 0):
            with st.spinner("Running analysis and building memory graph…"):
                report_state = asyncio.run(_session_end(dict(st.session_state)))
                report = report_state.get("report", {})
            st.session_state["report"] = report
            st.session_state["page"] = "report"
            st.rerun()


# ── Page: Report ──────────────────────────────────────────────────────────────
def _page_report():
    _header("report")

    report       = st.session_state["report"]
    candidate_id = st.session_state["candidate_id"]
    session_id   = st.session_state["session_id"]

    if not report:
        st.warning("No report found. Please complete an interview session first.")
        if st.button("← Back to start"):
            st.session_state["page"] = "upload"
            st.rerun()
        return

    rec_score  = report["recommendation_score"]
    score_hex  = "#10b981" if rec_score >= 75 else "#f59e0b" if rec_score >= 50 else "#ef4444"

    # ── Header row ─────────────────────────────────────────────────────────────
    col_title, col_score = st.columns([2.2, 1], gap="large")
    with col_title:
        st.markdown(f"""
        <h1 style="font-family:'IBM Plex Mono',monospace;font-size:1.9rem;
                   font-weight:600;color:#e2e8f0;margin-bottom:0.2rem;">
            Interview Report
        </h1>
        <p style="color:#475569;font-size:0.85rem;margin:0;">
            {candidate_id} · {session_id} · {len(report['scores'])} dimensions assessed
        </p>
        """, unsafe_allow_html=True)
    with col_score:
        st.markdown(f"""
        <div style="text-align:right;padding-top:0.4rem;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:2.8rem;
                         color:{score_hex};font-weight:600;line-height:1;">{rec_score}</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:1rem;
                         color:#334155;">/100</span><br/>
            <span style="font-size:0.7rem;color:#475569;text-transform:uppercase;
                         letter-spacing:0.09em;">recommendation score</span>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ── Summary ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="border-left:3px solid #00d4ff;padding-left:1.1rem;margin:0 0 1.8rem;">
        <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#00d4ff;
                     text-transform:uppercase;letter-spacing:0.1em;">Summary</span>
        <p style="color:#94a3b8;font-size:0.9rem;margin:0.5rem 0 0;line-height:1.65;">
            {report['summary']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Skill scores ───────────────────────────────────────────────────────────
    st.markdown("""
    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#334155;
                 text-transform:uppercase;letter-spacing:0.1em;">Skill Assessment</span>
    """, unsafe_allow_html=True)

    _score_cols = st.columns(len(report["scores"]))
    for col, s in zip(_score_cols, report["scores"]):
        strong = s["value"] >= 4
        col.metric(
            label=s["skill"],
            value=f"{s['value']}/5",
            delta="Strong" if strong else ("Gap" if s["value"] <= 2 else "Fair"),
            delta_color="normal" if strong else "inverse",
        )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # ── Gaps + Recommendation ─────────────────────────────────────────────────
    col_gaps, col_rec = st.columns([1.1, 1], gap="large")

    with col_gaps:
        st.markdown("""
        <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#334155;
                     text-transform:uppercase;letter-spacing:0.1em;">Skill Gaps</span>
        """, unsafe_allow_html=True)
        if report["gaps"]:
            import pandas as pd
            df = pd.DataFrame(report["gaps"])
            df.columns = ["Skill", "Description"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.markdown("<p style='color:#334155;font-size:0.85rem;'>No significant gaps identified.</p>",
                        unsafe_allow_html=True)

    with col_rec:
        st.markdown("""
        <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#334155;
                     text-transform:uppercase;letter-spacing:0.1em;">Recommendation</span>
        """, unsafe_allow_html=True)
        st.markdown(f"""
        <div style="border:1px solid rgba(255,255,255,0.07);border-radius:9px;
                    padding:1.1rem;margin-top:0.5rem;background:rgba(255,255,255,0.02);">
            <p style="color:#e2e8f0;font-size:0.88rem;margin:0 0 1rem;line-height:1.5;">
                {report['recommendation']}
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.progress(rec_score / 100)
        st.markdown(f"<p style='color:#334155;font-size:0.74rem;margin-top:0.3rem;'>"
                    f"{rec_score}% confidence</p>", unsafe_allow_html=True)

    # ── Memory graph ───────────────────────────────────────────────────────────
    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
    st.markdown("""
    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#334155;
                 text-transform:uppercase;letter-spacing:0.1em;">◈ Cognee Memory Graph</span>
    """, unsafe_allow_html=True)

    try:
        graph_html = _build_memory_graph(session_id, candidate_id)
        st.components.v1.html(graph_html, height=400, scrolling=False)
    except ImportError:
        st.markdown("""
        <div style="border:1px dashed rgba(255,255,255,0.08);border-radius:9px;
                    height:180px;display:flex;align-items:center;justify-content:center;">
            <span style="color:#1e293b;font-family:'IBM Plex Mono',monospace;font-size:0.78rem;">
                pip install pyvis  →  graph will render here
            </span>
        </div>
        """, unsafe_allow_html=True)

    # ── Footer actions ─────────────────────────────────────────────────────────
    st.divider()
    col_back, col_forget = st.columns([2, 1])

    with col_back:
        if st.button("← New Interview"):
            for k, v in _DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()

    with col_forget:
        if st.button("Forget candidate data (GDPR)", type="secondary", use_container_width=True):
            with st.spinner(f"Removing {candidate_id} from Cognee memory…"):
                asyncio.run(_forget(candidate_id))
            st.success(f"All data for '{candidate_id}' permanently deleted.")
            time.sleep(1.2)
            for k, v in _DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()


# ── Cognee config ─────────────────────────────────────────────────────────────
try:
    from agents.memory import _cognee_config
    _cognee_config()
except Exception:
    pass


# ── Router ────────────────────────────────────────────────────────────────────
_inject_css()

_page = st.session_state["page"]
if _page == "upload":
    _page_upload()
elif _page == "interview":
    _page_interview()
elif _page == "report":
    _page_report()
