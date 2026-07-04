"""
Cognee lifecycle wrappers.

Local JSON sidecar (~/.cognee_coach/sessions.json) stores structured data for
reliable recall() behaviour; Cognee graph/vector stores the semantic layer.
"""
import json
import os
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


def _load_env_file(env_path: Path | None = None) -> None:
    path = env_path or Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def _cognee_config():
    """
    LLM  → Groq (via LiteLLM groq/ prefix)
    Embeddings → FastEmbed (local, no API key — Groq has no embedding endpoint)
    """
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if load_dotenv and env_path.exists():
        load_dotenv(env_path, override=False)
    else:
        _load_env_file(env_path)

    groq_key = (
        os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LLM_API_KEY")
        or ""
    ).strip()

    os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"
    os.environ["GROQ_API_KEY"] = groq_key
    os.environ["OPENAI_API_KEY"] = groq_key
    os.environ["LLM_API_KEY"] = groq_key
    os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_API_BASE", "https://api.groq.com/openai/v1")

    # Tell Cognee/LiteLLM to use local FastEmbed for vectors
    os.environ["EMBEDDING_PROVIDER"] = "fastembed"
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-small-en-v1.5"
    try:
        import cognee
        cognee.config.set_llm_provider("openai")
        cognee.config.set_llm_model("groq/llama-3.3-70b-versatile")
        cognee.config.set_llm_api_key(groq_key)
        if hasattr(cognee.config, "set_llm_base_url"):
            cognee.config.set_llm_base_url("https://api.groq.com/openai/v1")
        try:
            cognee.config.set_embedding_model("BAAI/bge-small-en-v1.5")
            cognee.config.set_embedding_provider("fastembed")
        except AttributeError:
            pass  # env vars above handle it
    except Exception as e:
        print(f"[cognee] config warning: {e}")

try:
    from cognee.api.v1.search import SearchType
except ImportError:
    class SearchType:  # type: ignore
        INSIGHTS = "insights"

STORE = Path.home() / ".cognee_coach" / "sessions.json"
STORE.parent.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    return json.loads(STORE.read_text()) if STORE.exists() else {}


def _save(data: dict):
    STORE.write_text(json.dumps(data, indent=2))


# ── cognify ────────────────────────────────────────────────────────────────────

async def cognify_session(jd: str, resume: str, candidate_id: str, session_id: str):
    """Build entity graph from JD + resume. Called by intake agent."""
    text = (
        f"Candidate: {candidate_id}\nSession: {session_id}\n\n"
        f"Job Description:\n{jd}\n\nResume:\n{resume}"
    )
    try:
        import cognee
        _cognee_config()
        await cognee.add(text, dataset_name=f"candidate_{candidate_id}")
        await cognee.cognify()
    except Exception as e:
        print(f"[cognee] cognify warning: {e}")

    store = _load()
    store.setdefault(candidate_id, {"sessions": []})
    store[candidate_id]["jd"] = jd
    _save(store)


# ── remember ───────────────────────────────────────────────────────────────────

async def remember_qa(candidate_id: str, session_id: str, question: str, answer: str):
    """Store a Q&A pair. Called by interviewer agent every turn."""
    text = (
        f"Q&A for {candidate_id} / session {session_id}:\n"
        f"Q: {question}\nA: {answer}"
    )
    try:
        import cognee
        _cognee_config()
        await cognee.add(text, dataset_name=f"candidate_{candidate_id}")
        await cognee.cognify()
    except Exception as e:
        print(f"[cognee] remember warning: {e}")

    store = _load()
    store.setdefault(candidate_id, {"sessions": []})
    sessions = store[candidate_id]["sessions"]
    entry = next((s for s in sessions if s.get("session_id") == session_id), None)
    if not entry:
        entry = {
            "session_id": session_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "qa_pairs": [],
        }
        sessions.append(entry)
    entry["qa_pairs"].append({"q": question, "a": answer})
    _save(store)


# ── recall ─────────────────────────────────────────────────────────────────────

async def recall_prior(candidate_id: str) -> dict | None:
    """Retrieve prior session context. Called by interviewer at session start."""
    store = _load()
    data = store.get(candidate_id)
    if not data or not data.get("sessions"):
        return None

    sessions = data["sessions"]
    last = sessions[-1]

    cognee_context = None
    try:
        import cognee
        _cognee_config()
        results = await cognee.search(
            f"interview performance and skills for candidate {candidate_id}",
            search_type=SearchType.INSIGHTS,
        )
        if results:
            cognee_context = str(results[:2])
    except Exception:
        pass

    prior_report = last.get("report") or {}
    gaps = [g["skill"] for g in prior_report.get("gaps", [])]
    scores = prior_report.get("scores", [])
    top = max(scores, key=lambda s: s["value"], default=None)
    low = min(scores, key=lambda s: s["value"], default=None)

    note_parts = []
    if top:
        note_parts.append(f"Strong in {top['skill']} ({top['value']}/5)")
    if low and low != top:
        note_parts.append(f"gap in {low['skill']} ({low['value']}/5)")
    if gaps:
        note_parts.append(f"Flag gaps: {', '.join(gaps)}")
    note_parts.append("Do not repeat questions already answered.")

    return {
        "candidate_id": candidate_id,
        "session_date": last.get("date", "prior session"),
        "note": ". ".join(note_parts) if note_parts else "Prior session on record.",
        "sessions": sessions,
        "last_session": last,
        "cognee_context": cognee_context,
    }


# ── memify ─────────────────────────────────────────────────────────────────────

async def memify_session(session_id: str, candidate_id: str, report: dict):
    """Store session quality for role-level learning. Called by analysis agent."""
    text = (
        f"Post-interview quality report\n"
        f"Candidate: {candidate_id} | Session: {session_id}\n"
        f"{json.dumps(report, indent=2)}"
    )
    try:
        import cognee
        _cognee_config()
        await cognee.add(text, dataset_name="role_memory")
        await cognee.cognify()
    except Exception as e:
        print(f"[cognee] memify warning: {e}")

    store = _load()
    if candidate_id in store:
        for s in store[candidate_id].get("sessions", []):
            if s.get("session_id") == session_id:
                s["report"] = report
                break
    _save(store)


# ── forget ─────────────────────────────────────────────────────────────────────

async def forget_candidate(candidate_id: str):
    """GDPR: remove candidate data from Cognee and local store."""
    try:
        import cognee
        _cognee_config()
        try:
            await cognee.prune.prune_dataset(f"candidate_{candidate_id}")
        except AttributeError:
            await cognee.prune.prune_system(metadata=True)
    except Exception as e:
        print(f"[cognee] forget warning: {e}")

    store = _load()
    store.pop(candidate_id, None)
    _save(store)
