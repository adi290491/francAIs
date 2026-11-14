"""Validation of audio files (uploads and microphone recordings), run before any model call."""

from pathlib import Path
from typing import Literal

from tutor.core.errors import AudioValidationError

AudioSource = Literal["upload", "recording"]

# Uploads keep the v1 rule. Gradio's microphone recorder always hands back `audio.wav`.
ALLOWED_EXTENSIONS: dict[str, frozenset[str]] = {
    "upload": frozenset({".mp3"}),
    "recording": frozenset({".wav"}),
}

_NOUN = {"upload": "uploaded file", "recording": "recording"}


def validate_audio(path: str | Path, *, max_bytes: int, source: AudioSource = "upload") -> Path:
    """Check that `path` is a non-empty file of the right type for `source`, within `max_bytes`.

    Returns the path as a `Path`; raises `AudioValidationError` with a user-facing message.
    """
    if source not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unknown audio source: {source!r}")
    audio = Path(path)
    noun = _NOUN[source]

    if audio.suffix.lower() not in ALLOWED_EXTENSIONS[source]:
        shown = audio.suffix or "no extension"
        if source == "upload":
            raise AudioValidationError(f"Only .mp3 files are supported (got {shown}).")
        raise AudioValidationError(f"The recording must be a .wav file (got {shown}).")

    if not audio.is_file():
        again = "upload it" if source == "upload" else "record it"
        raise AudioValidationError(f"The {noun} could not be found. Please {again} again.")

    size = audio.stat().st_size
    if size == 0:
        if source == "upload":
            raise AudioValidationError(
                "The uploaded file is empty. Please choose a different .mp3."
            )
        raise AudioValidationError("The recording is empty. Please record again.")
    if size > max_bytes:
        raise AudioValidationError(
            f"The {noun} is {_mb(size)} MB, which is over the {_mb(max_bytes)} MB limit. "
            "Please use a shorter recording."
        )

    return audio


def _mb(n_bytes: int) -> str:
    return f"{n_bytes / (1024 * 1024):.1f}"
