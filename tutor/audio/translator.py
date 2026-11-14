"""French audio to English text: transcribe, then translate."""

from pathlib import Path
from typing import Any

from huggingface_hub import InferenceClient

from tutor.audio import transcriber
from tutor.audio.validation import AudioSource
from tutor.core.client import get_client
from tutor.core.config import Settings, get_settings
from tutor.core.errors import InferenceError
from tutor.core.inference import inference_errors


def translate_audio(
    audio_path: str | Path,
    *,
    source: AudioSource = "upload",
    session: Any | None = None,
    client: InferenceClient | None = None,
    settings: Settings | None = None,
) -> str:
    """Transcribe French audio (via `transcriber.transcribe`) and translate it to English.

    `session` is used for the transcription call and `client` for the translation call.
    """
    french = transcriber.transcribe(audio_path, source=source, session=session, settings=settings)
    return translate_text(french, client=client, settings=settings)


def translate_text(
    french: str,
    *,
    client: InferenceClient | None = None,
    settings: Settings | None = None,
) -> str:
    """Translate French text to English. Raises `InferenceError` on failure."""
    settings = settings or get_settings()
    client = client or get_client()

    with inference_errors("translation"):
        result = client.translation(french, model=settings.translation_model)

    text = (result.translation_text or "").strip()
    if not text:
        raise InferenceError("The translation came back empty. Please try again.")
    return text
