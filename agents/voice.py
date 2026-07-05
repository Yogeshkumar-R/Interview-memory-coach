"""
Voice utilities — Groq Whisper STT via the Groq SDK.
No local model download required; transcription runs on Groq's servers.
"""
from agents.base import client


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio with Groq whisper-large-v3.
    filename hint tells the API which codec to expect (webm/ogg/wav/mp3/m4a).
    Returns empty string on silence or failure.
    """
    if not audio_bytes:
        return ""
    try:
        result = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=(filename, audio_bytes),
            response_format="text",
        )
        text = getattr(result, "text", result) or ""
        return str(text).strip()
    except Exception as exc:
        print(f"[voice] transcription error: {exc}")
        return ""
