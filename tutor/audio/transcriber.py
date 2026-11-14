"""French speech-to-text, with word-level timings."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tutor.audio.validation import AudioSource, validate_audio
from tutor.core.asr_api import request_transcription
from tutor.core.config import Settings, get_settings
from tutor.core.errors import InferenceError
from tutor.core.inference import inference_errors

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Word:
    """One spoken word (fillers included) and when it was said, in seconds from the start."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Transcript:
    """The French text plus per-word timings (empty when the provider returned none)."""

    text: str
    words: tuple[Word, ...] = ()
    duration: float | None = None


def transcribe_detailed(
    audio_path: str | Path,
    *,
    source: AudioSource = "upload",
    session: Any | None = None,
    settings: Settings | None = None,
) -> Transcript:
    """Validate the audio for its `source` and transcribe it to French, with word timings.

    Whisper is forced to French at temperature 0 and primed to keep fillers (see `asr_api`).
    `session` and `settings` default to the shared ones. Raises `AudioValidationError` or
    `InferenceError`.
    """
    settings = settings or get_settings()
    audio = validate_audio(audio_path, max_bytes=settings.max_upload_bytes, source=source)

    with inference_errors("transcription"):
        payload = request_transcription(audio, settings=settings, session=session)

    if not isinstance(payload, dict):
        logger.error("transcription returned a %s, expected a JSON object", type(payload).__name__)
        raise InferenceError("The transcription service returned an unexpected response.")

    text = str(payload.get("text") or "").strip()
    if not text:
        raise InferenceError("No speech was detected in the recording.")

    return Transcript(
        text=text,
        words=_parse_words(payload.get("words")),
        duration=_as_float(payload.get("duration")),
    )


def transcribe(
    audio_path: str | Path,
    *,
    source: AudioSource = "upload",
    session: Any | None = None,
    settings: Settings | None = None,
) -> str:
    """Transcribe to French text only (the v1 contract, reused by the translator)."""
    return transcribe_detailed(audio_path, source=source, session=session, settings=settings).text


def _parse_words(raw: Any) -> tuple[Word, ...]:
    """Turn the provider's `words` list into `Word`s, joining split fragments.

    Whisper marks a new word with a leading space, so a token without one continues the
    previous word (`" s"` + `"'il"` -> `"s'il"`). Malformed entries are skipped.
    """
    if not isinstance(raw, list):
        return ()

    tokens: list[tuple[str, float, float]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        token = item.get("word")
        start, end = _as_float(item.get("start")), _as_float(item.get("end"))
        if not isinstance(token, str) or not token.strip() or start is None or end is None:
            continue
        if end < start:
            continue
        tokens.append((token, start, end))

    # If no token has a leading space, the provider doesn't use that convention; don't merge.
    spaced = any(token[:1].isspace() for token, _, _ in tokens)

    words: list[Word] = []
    for token, start, end in tokens:
        if spaced and words and not token[:1].isspace():
            prev = words[-1]
            words[-1] = Word(prev.text + token.strip(), prev.start, max(prev.end, end))
        else:
            words.append(Word(token.strip(), start, end))
    return tuple(words)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
