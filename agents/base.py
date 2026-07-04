import os
import time

try:
    from groq import Groq
except ImportError:  # pragma: no cover - dependency may be absent in some environments
    Groq = None

MODEL = "llama-3.3-70b-versatile"
client = None


def _build(messages: list, system: str) -> list:
    if system:
        return [{"role": "system", "content": system}] + messages
    return messages


def _get_client():
    global client
    if client is not None:
        return client

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or Groq is None:
        return None

    client = Groq(api_key=api_key)
    return client


def chat(messages: list, system: str = "", max_tokens: int = 1024) -> str:
    if not _get_client():
        return (
            "Groq API key is not configured. "
            "Set GROQ_API_KEY to enable live interview generation."
        )

    for attempt in range(3):
        try:
            resp = _get_client().chat.completions.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=_build(messages, system),
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt < 2 and ("rate" in str(e).lower() or "429" in str(e)):
                time.sleep(2 ** attempt)
            else:
                return f"LLM request failed: {e}"


def stream_chat(messages: list, system: str = "", max_tokens: int = 512):
    """Sync generator of text chunks — pass directly to st.write_stream."""
    client = _get_client()
    if not client:
        yield (
            "Groq API key is not configured. "
            "Set GROQ_API_KEY to enable live interview generation."
        )
        return

    stream = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=_build(messages, system),
        stream=True,
    )
    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content
