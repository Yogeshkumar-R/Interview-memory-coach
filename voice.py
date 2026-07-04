import io
import os
import tempfile
import wave
from pathlib import Path
from typing import Optional

import numpy as np


class VoiceUnavailableError(RuntimeError):
    pass


def audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    if audio.size == 0:
        return b""

    audio = np.asarray(audio)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    audio = np.clip(audio, -1.0, 1.0)
    pcm = np.round(audio * 32767).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())

    return buffer.getvalue()


def transcribe_audio(audio_bytes: bytes, model: str = "tiny") -> str:
    if not audio_bytes:
        return ""

    try:
        import whisper
    except ImportError as exc:
        raise VoiceUnavailableError("whisper is not installed") from exc

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        model_obj = whisper.load_model(model)
        result = model_obj.transcribe(tmp_path)
        os.unlink(tmp_path)
        return result.get("text", "").strip()
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return ""


def speak_text(text: str, output_path: Optional[str] = None) -> Optional[str]:
    if not text.strip():
        return None

    try:
        import pyttsx3
    except ImportError:
        return None

    engine = pyttsx3.init()
    if output_path:
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        return output_path

    engine.say(text)
    engine.runAndWait()
    return None
