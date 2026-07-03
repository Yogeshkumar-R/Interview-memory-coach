import os
import time
from groq import Groq

MODEL = "llama-3.3-70b-versatile"
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def _build(messages: list, system: str) -> list:
    if system:
        return [{"role": "system", "content": system}] + messages
    return messages


def chat(messages: list, system: str = "", max_tokens: int = 1024) -> str:
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=_build(messages, system),
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt < 2 and ("rate" in str(e).lower() or "429" in str(e)):
                time.sleep(2 ** attempt)
            else:
                raise


def stream_chat(messages: list, system: str = "", max_tokens: int = 512):
    """Sync generator of text chunks — pass directly to st.write_stream."""
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
