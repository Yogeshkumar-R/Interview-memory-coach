"""
Seed 2 synthetic prior sessions for alice_jones.
Run BEFORE the demo: python seed_memory.py
"""
import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

STORE = Path.home() / ".cognee_coach" / "sessions.json"
STORE.parent.mkdir(parents=True, exist_ok=True)

SEED = {
    "alice_jones": {
        "jd": "Senior Backend Engineer: Python, system design, distributed systems, PostgreSQL",
        "sessions": [
            {
                "session_id": "sess_SEED01",
                "date": str(date.today() - timedelta(days=16)),
                "qa_pairs": [
                    {
                        "q": "Describe your experience with distributed systems.",
                        "a": "Worked with Redis and RabbitMQ but mostly single-region. Haven't dealt with cross-region consensus in production.",
                    },
                    {
                        "q": "How do you handle database performance at scale?",
                        "a": "Indexing, query optimisation, connection pooling. Comfortable with PostgreSQL EXPLAIN ANALYZE.",
                    },
                    {
                        "q": "Walk me through designing a URL shortener at global scale.",
                        "a": "Hash function, store in Postgres, Redis cache layer. Struggled a bit when asked about multi-region consistency.",
                    },
                ],
                "report": {
                    "summary": (
                        "Strong Python and database fundamentals. "
                        "System design at global scale is an area for growth."
                    ),
                    "scores": [
                        {"skill": "Python",              "value": 5},
                        {"skill": "System Design",       "value": 2},
                        {"skill": "Databases",           "value": 4},
                        {"skill": "Distributed Systems", "value": 2},
                        {"skill": "Communication",       "value": 4},
                    ],
                    "gaps": [
                        {"skill": "System Design",       "description": "Struggles with ambiguous scale requirements"},
                        {"skill": "Distributed Systems", "description": "Limited production experience with consensus"},
                    ],
                    "recommendation": "Advance to technical round — focus on distributed systems",
                    "recommendation_score": 65,
                },
            },
            {
                "session_id": "sess_SEED02",
                "date": str(date.today() - timedelta(days=3)),
                "qa_pairs": [
                    {
                        "q": "What have you done since our last conversation around distributed systems?",
                        "a": "Read Designing Data-Intensive Applications cover to cover and built a toy Raft implementation in Python.",
                    },
                    {
                        "q": "Explain the CAP theorem with a production example.",
                        "a": "In a network partition you choose between consistency and availability. Banking systems should choose consistency — stale balance data is worse than an error.",
                    },
                ],
                "report": None,
            },
        ],
    }
}


async def seed():
    # Write structured data to local sidecar
    existing = json.loads(STORE.read_text()) if STORE.exists() else {}
    existing.update(SEED)
    STORE.write_text(json.dumps(existing, indent=2))
    print(f"[seed] Wrote to {STORE}")

    # Ingest into Cognee
    try:
        import cognee
        from agents.memory import _cognee_config
        _cognee_config()

        for cid, data in SEED.items():
            for session in data["sessions"]:
                parts = [f"Candidate: {cid}", f"Session: {session['session_id']}"]
                for qa in session["qa_pairs"]:
                    parts.append(f"Q: {qa['q']}\nA: {qa['a']}")
                await cognee.add("\n".join(parts), dataset_name=f"candidate_{cid}")
            print(f"[seed] Added {cid} to Cognee")

        await cognee.cognify()
        print("[seed] cognify() complete")
    except Exception as e:
        print(f"[seed] Cognee not available — local sidecar only: {e}")

    print("\n[seed] Done. Use candidate_id 'alice_jones' to see recall() in action.")


asyncio.run(seed())
