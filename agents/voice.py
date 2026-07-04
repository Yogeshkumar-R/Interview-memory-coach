"""
Voice utilities — Groq Whisper STT + pyttsx3 TTS.
No local model download required; Whisper runs on Groq's servers.
"""
from agents.base import client


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio with Groq whisper-large-v3.
    filename hint tells the API which codec to expect (webm/ogg/wav/mp3/m4a).
    Returns empty string on silence; returns error string starting with '[' on failure.
    """
    if not audio_bytes:
        return ""
    try:
        result = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=(filename, audio_bytes),
            response_format="text",
        )
        # response_format="text" returns a plain str; guard against future SDK changes
        text = getattr(result, "text", result) or ""
        return str(text).strip()
    except Exception as exc:
        print(f"[voice] transcription error: {exc}")
        return ""


def speak_text(text: str) -> None:
    """TTS via pyttsx3 (local, offline). Silent no-op if not installed."""
    if not text.strip():
        return
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass
