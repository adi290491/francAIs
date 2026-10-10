"""Validation of uploaded audio files, run before any model call."""

from pathlib import Path

from tutor.core.errors import AudioValidationError

ALLOWED_EXTENSIONS = frozenset({".mp3"})


def validate_audio(path: str | Path, *, max_bytes: int) -> Path:
    """Check that `path` is a non-empty `.mp3` no larger than `max_bytes`.

    Returns the path as a `Path`; raises `AudioValidationError` with a user-facing message.
    """
    audio = Path(path)

    if audio.suffix.lower() not in ALLOWED_EXTENSIONS:
        shown = audio.suffix or "no extension"
        raise AudioValidationError(f"Only .mp3 files are supported (got {shown}).")

    if not audio.is_file():
        raise AudioValidationError("The uploaded file could not be found. Please upload it again.")

    size = audio.stat().st_size
    if size == 0:
        raise AudioValidationError("The uploaded file is empty. Please choose a different .mp3.")
    if size > max_bytes:
        raise AudioValidationError(
            f"The file is {_mb(size)} MB, which is over the {_mb(max_bytes)} MB limit. "
            "Please upload a shorter recording."
        )

    return audio


def _mb(n_bytes: int) -> str:
    return f"{n_bytes / (1024 * 1024):.1f}"
