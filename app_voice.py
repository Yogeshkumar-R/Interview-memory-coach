import asyncio
import uuid

import av
import numpy as np
import streamlit as st
from streamlit_webrtc import AudioProcessorBase, WebRtcMode, webrtc_streamer

from agents.memory import cognify_session, forget_candidate, memify_session, recall_prior, remember_qa
from agents.voice import audio_to_wav_bytes, speak_text, transcribe_audio

st.set_page_config(page_title="Interview Memory Coach Voice", page_icon="🎙️", layout="wide")


def _inject_css():
    st.markdown(
        """
        <style>
        .stApp { background: #07111f; color: #e2e8f0; }
        .block-container { padding-top: 1.5rem; max-width: 1120px; }
        .step-pill {
            display: inline-block;
            padding: 0.28rem 0.75rem;
            border-radius: 999px;
            border: 1px solid rgba(0,212,255,0.25);
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #94a3b8;
            margin-right: 0.35rem;
        }
        .step-pill.active { color: #00d4ff; border-color: rgba(0,212,255,0.5); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _header(active: str):
    steps = [("upload", "01 · INTAKE"), ("interview", "02 · INTERVIEW"), ("report", "03 · REPORT")]
    badges = []
    for key, label in steps:
        css_class = "step-pill active" if key == active else "step-pill"
        badges.append(f'<span class="{css_class}">{label}</span>')
    st.markdown(
        f"""
        <div style="margin-bottom: 1.4rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;flex-wrap:wrap;">
                <div style="font-family:IBM Plex Mono,monospace;font-size:0.78rem;color:#00d4ff;letter-spacing:0.16em;">◈ VOICE MEMORY COACH</div>
                <div>{''.join(badges)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


DEFAULT_QUESTIONS = [
    "Tell me about your background and how it relates to this role.",
    "Describe a challenging backend system you have worked on.",
    "How do you approach debugging production issues at scale?",
]


class AudioRecorder(AudioProcessorBase):
    def __init__(self):
        self.audio_chunks = []
        self.sample_rate = 16000

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        audio = frame.to_ndarray()
        if audio.size:
            self.audio_chunks.append(audio)
            self.sample_rate = getattr(frame, "sample_rate", self.sample_rate)
        return frame


_DEFAULTS = {
    "page": "upload",
    "session_id": None,
    "candidate_id": "",
    "jd_text": "",
    "resume_text": "",
    "questions": [],
    "question_index": 0,
    "answers": [],
    "voice_messages": [],
    "captured_audio": None,
    "prior_context": None,
    "report": None,
    "interview_ended": False,
}

for key, value in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def _reset_interview_state():
    st.session_state.update(
        {
            "session_id": None,
            "candidate_id": "",
            "jd_text": "",
            "resume_text": "",
            "questions": [],
            "question_index": 0,
            "answers": [],
            "voice_messages": [],
            "captured_audio": None,
            "prior_context": None,
            "report": None,
            "interview_ended": False,
        }
    )


def _record_answer(question: str, answer: str):
    st.session_state["answers"].append(answer)
    st.session_state["voice_messages"].append(("You", answer))
    st.session_state["voice_messages"].append(("Coach", "Thanks. I’ll move to the next question."))
    st.session_state["question_index"] += 1
    st.session_state["interview_ended"] = st.session_state["question_index"] >= len(st.session_state["questions"])

    try:
        asyncio.run(
            remember_qa(
                candidate_id=st.session_state["candidate_id"],
                session_id=st.session_state["session_id"],
                question=question,
                answer=answer,
            )
        )
    except Exception as exc:
        st.session_state["voice_messages"].append(("Coach", f"Memory note skipped: {exc}"))


def _page_upload():
    _header("upload")
    st.title("Stage 1 · Intake")
    st.caption("Enter the candidate details and start a voice-first interview session.")

    candidate_id = st.text_input("Candidate ID", value=st.session_state.get("candidate_id", ""), placeholder="e.g. alice_jones")
    jd_text = st.text_area("Job Description", value=st.session_state.get("jd_text", ""), height=180, placeholder="Paste the role description here…")
    resume_text = st.text_area("Resume Summary", value=st.session_state.get("resume_text", ""), height=180, placeholder="Paste the candidate resume summary…")

    can_start = bool(candidate_id.strip() and jd_text.strip())
    if st.button("Start Interview →", disabled=not can_start, use_container_width=True):
        session_id = f"voice_{uuid.uuid4().hex[:6].upper()}"
        st.session_state.update(
            {
                "page": "interview",
                "session_id": session_id,
                "candidate_id": candidate_id.strip(),
                "jd_text": jd_text.strip(),
                "resume_text": resume_text.strip(),
                "questions": DEFAULT_QUESTIONS,
                "question_index": 0,
                "answers": [],
                "voice_messages": [("Coach", "Welcome. I’ll guide you through the interview step by step.")],
                "captured_audio": None,
                "prior_context": None,
                "report": None,
                "interview_ended": False,
            }
        )
        try:
            asyncio.run(cognify_session(jd_text.strip(), resume_text.strip(), candidate_id.strip(), session_id))
        except Exception as exc:
            st.session_state["voice_messages"].append(("Coach", f"Cognee intake note skipped: {exc}"))
        st.rerun()


def _page_interview():
    _header("interview")
    st.title("Stage 2 · Interview")
    st.caption("Answer out loud, type a fallback response, or move to the next question.")

    if not st.session_state.get("questions"):
        st.info("No questions loaded yet. Go back to intake and start a new session.")
        if st.button("← Back to intake"):
            st.session_state["page"] = "upload"
            st.rerun()
        return

    current_question_index = min(st.session_state.get("question_index", 0), len(st.session_state["questions"]) - 1)
    current_question = st.session_state["questions"][current_question_index] if st.session_state["questions"] else ""

    if not st.session_state.get("prior_context") and st.session_state.get("candidate_id"):
        try:
            st.session_state["prior_context"] = asyncio.run(recall_prior(st.session_state["candidate_id"]))
        except Exception:
            st.session_state["prior_context"] = None

    col_left, col_right = st.columns([1.15, 1], gap="large")
    with col_left:
        st.markdown(f"### Current question\n{current_question}")
        if st.button("Speak current question"):
            speak_text(current_question)

        prior_context = st.session_state.get("prior_context")
        if prior_context:
            st.markdown(
                f"""
                <div style="border:1px solid rgba(0,212,255,0.3);border-radius:9px;padding:0.9rem 1rem;background:rgba(0,212,255,0.06);margin-bottom:1rem;">
                    <div style="font-family:IBM Plex Mono,monospace;font-size:0.68rem;color:#00d4ff;letter-spacing:0.12em;text-transform:uppercase;">◈ Cognee Recall</div>
                    <div style="font-size:0.84rem;color:#94a3b8;margin-top:0.35rem;">{prior_context.get('note', 'Prior session context loaded.')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()
        for speaker, text in st.session_state.get("voice_messages", []):
            st.markdown(f"**{speaker}:** {text}")

    with col_right:
        st.markdown("### Answer")
        st.markdown("Allow microphone access, then capture your answer.")
        webrtc_ctx = webrtc_streamer(
            key="voice-recorder",
            mode=WebRtcMode.SENDONLY,
            media_stream_constraints={"video": False, "audio": True},
            audio_processor_factory=AudioRecorder,
            async_processing=True,
        )

        if st.button("Capture answer"):
            if webrtc_ctx and webrtc_ctx.audio_processor:
                chunks = getattr(webrtc_ctx.audio_processor, "audio_chunks", [])
                if chunks:
                    audio = np.concatenate(chunks, axis=0)
                    sample_rate = getattr(webrtc_ctx.audio_processor, "sample_rate", 16000)
                    st.session_state["captured_audio"] = audio_to_wav_bytes(audio, sample_rate=sample_rate)
                    with st.spinner("Transcribing audio..."):
                        try:
                            transcript = transcribe_audio(st.session_state["captured_audio"])
                        except Exception as exc:
                            transcript = f"Voice transcription unavailable: {exc}"
                    if transcript:
                        _record_answer(current_question, transcript)
                        st.success("Answer captured")
                        st.rerun()
                    else:
                        st.warning("No speech detected. Try a clearer recording.")
                else:
                    st.warning("No audio captured yet. Please allow microphone access and speak clearly.")
            else:
                st.warning("Microphone capture is not ready yet. Refresh the page and allow access.")

        if st.button("Next question"):
            st.session_state["voice_messages"].append(("Coach", "Let’s move to the next question."))
            st.session_state["question_index"] += 1
            st.session_state["interview_ended"] = st.session_state["question_index"] >= len(st.session_state["questions"])
            st.rerun()

        answer_text = st.text_area("Type your answer here if microphone is unavailable", height=120, key="answer_text")
        if st.button("Submit typed answer") and answer_text.strip():
            _record_answer(current_question, answer_text.strip())
            st.session_state.pop("answer_text", None)
            st.rerun()

        st.markdown("---")
        st.markdown("### Voice fallback")
        uploaded_file = st.file_uploader("Or upload a voice clip", type=["wav", "mp3", "m4a", "ogg"])
        if uploaded_file is not None:
            audio_bytes = uploaded_file.read()
            with st.spinner("Transcribing audio..."):
                try:
                    transcript = transcribe_audio(audio_bytes)
                except Exception as exc:
                    transcript = f"Voice transcription unavailable: {exc}"
            if transcript:
                _record_answer(current_question, transcript)
                st.success("Answer captured")
                st.rerun()
            else:
                st.warning("No speech detected. Try a clearer recording.")

        st.divider()
        st.progress(min(st.session_state["question_index"] / max(len(st.session_state["questions"]), 1), 1.0))
        st.caption(f"{min(st.session_state['question_index'], len(st.session_state['questions']))}/{len(st.session_state['questions'])} questions advanced")

        if st.button("Generate Report →", use_container_width=True):
            answer_texts = " ".join(st.session_state["answers"])
            score = min(100, 55 + len(st.session_state["answers"]) * 12)
            if any(term in answer_texts.lower() for term in ["design", "scale", "debug", "lead", "system"]):
                score += 5
            report = {
                "recommendation_score": score,
                "summary": f"{st.session_state['candidate_id']} completed a voice interview with {len(st.session_state['answers'])} answers.",
                "answers": st.session_state["answers"],
                "questions": st.session_state["questions"],
            }
            try:
                asyncio.run(memify_session(st.session_state["session_id"], st.session_state["candidate_id"], report))
            except Exception:
                pass
            st.session_state["report"] = report
            st.session_state["page"] = "report"
            st.rerun()


def _build_memory_graph(session_id: str, candidate_id: str) -> str:
    from pyvis.network import Network

    net = Network(height="380px", width="100%", bgcolor="#07111f", font_color="#94a3b8")
    net.set_options(
        """
        {
          "nodes": {"font": {"size": 11}, "borderWidth": 1, "shape": "dot"},
          "edges": {"smooth": {"type": "continuous"}, "font": {"size": 9, "align": "middle"}, "color": {"color": "rgba(100,116,139,0.5)"}},
          "physics": {"stabilization": {"iterations": 180}}
        }
        """
    )

    nodes = [
        (candidate_id, "Candidate", "#00d4ff", 22),
        ("senior_backend", "Role: Senior Backend", "#7c3aed", 18),
        ("skill_python", "Python", "#10b981", 14),
        ("skill_sysdesign", "System Design", "#f59e0b", 14),
        ("skill_distributed", "Distributed Systems", "#f59e0b", 14),
        (session_id, f"Session {session_id}", "#334155", 16),
    ]
    for nid, label, color, size in nodes:
        net.add_node(nid, label=label, color=color, size=size)

    edges = [
        (candidate_id, "skill_python", "has_skill"),
        (candidate_id, "skill_sysdesign", "has_skill"),
        (candidate_id, "senior_backend", "applied_for"),
        ("senior_backend", "skill_python", "requires_skill"),
        ("senior_backend", "skill_sysdesign", "requires_skill"),
        ("senior_backend", "skill_distributed", "requires_skill"),
        (session_id, candidate_id, "belongs_to"),
    ]
    for src, dst, label in edges:
        net.add_edge(src, dst, title=label, label=label)

    return net.generate_html(notebook=False)


def _page_report():
    _header("report")
    st.title("Stage 3 · Report")
    st.caption("Review the interview outcome and continue to the next candidate.")

    report = st.session_state.get("report")
    if not report:
        st.info("No report available yet. Finish the interview to generate one.")
        if st.button("← Back to interview"):
            st.session_state["page"] = "interview"
            st.rerun()
        return

    st.metric("Candidate", st.session_state.get("candidate_id", ""))
    st.metric("Recommendation score", f"{report['recommendation_score']}/100")

    st.markdown("### Summary")
    st.write(report["summary"])

    st.markdown("### Q&A snapshot")
    for idx, (question, answer) in enumerate(zip(report["questions"], report["answers"]), start=1):
        st.markdown(f"**{idx}. {question}**")
        st.write(answer)

    st.markdown("### Cognee memory graph")
    try:
        graph_html = _build_memory_graph(st.session_state.get("session_id", "voice_session"), st.session_state.get("candidate_id", "candidate"))
        st.components.v1.html(graph_html, height=400, scrolling=False)
    except ImportError:
        st.info("Install pyvis to render the memory graph here.")

    st.divider()
    col_back, col_forget = st.columns([2, 1])

    with col_back:
        if st.button("← Start new interview"):
            _reset_interview_state()
            st.session_state["page"] = "upload"
            st.rerun()

    with col_forget:
        if st.button("Forget candidate data (GDPR)", type="secondary", use_container_width=True):
            with st.spinner(f"Removing {st.session_state.get('candidate_id', '')} from Cognee memory…"):
                asyncio.run(forget_candidate(st.session_state.get("candidate_id", "")))
            st.success(f"All data for '{st.session_state.get('candidate_id', '')}' permanently deleted.")
            _reset_interview_state()
            st.session_state["page"] = "upload"
            st.rerun()


_inject_css()

page = st.session_state.get("page", "upload")
if page == "upload":
    _page_upload()
elif page == "interview":
    _page_interview()
elif page == "report":
    _page_report()
else:
    st.session_state["page"] = "upload"
    st.rerun()
