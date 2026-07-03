"""
Day 1 validation — run this before building anything else.
All checks must pass before proceeding.
"""
import asyncio
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


async def main():
    ok, fail = [], []

    # 1. API key present
    if os.getenv("GROQ_API_KEY"):
        ok.append("GROQ_API_KEY set")
    else:
        fail.append("GROQ_API_KEY missing — add to .env")

    # 2. Anthropic SDK
    try:
        from agents.base import chat
        resp = chat([{"role": "user", "content": "Reply with the single word: OK"}], max_tokens=10)
        ok.append(f"Groq SDK: {resp.strip()}")
    except Exception as e:
        fail.append(f"Anthropic SDK: {e}")

    # 3. Cognee add + cognify
    try:
        import cognee
        from agents.memory import _cognee_config
        _cognee_config()
        await cognee.add("Smoke test candidate. Skills: Python, FastAPI.", dataset_name="smoke_test")
        await cognee.cognify()
        ok.append("Cognee cognify()")
    except Exception as e:
        fail.append(f"Cognee cognify: {e}")

    # 4. recall (local sidecar)
    try:
        from agents.memory import recall_prior
        ctx = await recall_prior("nonexistent_candidate_xyz")
        ok.append(f"recall() cold start: {ctx}")
    except Exception as e:
        fail.append(f"recall: {e}")

    # 5. PyMuPDF
    try:
        import fitz
        ok.append(f"PyMuPDF {fitz.__version__}")
    except ImportError:
        fail.append("PyMuPDF not installed — pip install PyMuPDF")

    # 6. pyvis
    try:
        import pyvis
        ok.append(f"pyvis {pyvis.__version__}")
    except ImportError:
        fail.append("pyvis not installed — pip install pyvis")

    # 7. streamlit
    try:
        import streamlit
        ok.append(f"streamlit {streamlit.__version__}")
    except ImportError:
        fail.append("streamlit not installed")

    print("\n-- Results --")
    for msg in ok:
        print(f"  [OK]   {msg}")
    for msg in fail:
        print(f"  [FAIL] {msg}")

    if fail:
        print(f"\n{len(fail)} check(s) failed. Fix before building.")
        sys.exit(1)
    else:
        print(f"\nAll {len(ok)} checks passed. Foundation solid.")


asyncio.run(main())
