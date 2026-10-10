"""French speech-to-text."""

from pathlib import Path

from huggingface_hub import InferenceClient

from tutor.audio.validation import validate_audio
from tutor.core.client import get_client
from tutor.core.config import Settings, get_settings
from tutor.core.errors import InferenceError
from tutor.core.inference import inference_errors


def transcribe(
    audio_path: str | Path,
    *,
    client: InferenceClient | None = None,
    settings: Settings | None = None,
) -> str:
    """Validate the upload and transcribe it to French text.

    `client` and `settings` default to the shared process-wide instances.
    Raises `AudioValidationError` or `InferenceError`.
    """
    settings = settings or get_settings()
    audio = validate_audio(audio_path, max_bytes=settings.max_upload_bytes)
    client = client or get_client()

    with inference_errors("transcription"):
        # Pass a str, not a Path: some provider helpers (e.g. fal-ai) only accept str or bytes.
        result = client.automatic_speech_recognition(str(audio), model=settings.asr_model)

    text = (result.text or "").strip()
    if not text:
        raise InferenceError("No speech was detected in the recording.")
    return text
