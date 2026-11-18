"""Validation of audio files (uploads and microphone recordings), run before any model call."""

import array
import logging
import sys
import wave
from pathlib import Path
from typing import Literal

from tutor.core.errors import AudioValidationError

logger = logging.getLogger(__name__)

AudioSource = Literal["upload", "recording", "file"]

# Uploads keep the v1 rule. Gradio's microphone recorder always hands back `audio.wav`.
# "file" is audio sent by a program (the MCP tools), which may be either kind.
ALLOWED_EXTENSIONS: dict[str, frozenset[str]] = {
    "upload": frozenset({".mp3"}),
    "recording": frozenset({".wav"}),
    "file": frozenset({".mp3", ".wav"}),
}

_NOUN = {"upload": "uploaded file", "recording": "recording", "file": "audio file"}

# A recording whose loudest sample is below -60 dBFS has no speech in it: the microphone was
# muted, disconnected, or not the one being spoken into. Whisper invents text for silence
# (e.g. « Sous-titres réalisés par la communauté d'Amara.org »), so stop before the call.
SILENCE_PEAK = 10 ** (-60 / 20)  # fraction of full scale
SILENT_RECORDING_MESSAGE = (
    "No sound was picked up in the recording. Check that the microphone selected in the "
    "recorder is the one you are speaking into and that it isn't muted, then record again."
)
SILENT_FILE_MESSAGE = "The audio file is silent. Please send a .wav or .mp3 with speech in it."


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
        if source == "file":
            raise AudioValidationError(f"Only .mp3 or .wav files are supported (got {shown}).")
        raise AudioValidationError(f"The recording must be a .wav file (got {shown}).")

    if not audio.is_file():
        again = {"upload": "upload it", "recording": "record it", "file": "send it"}[source]
        raise AudioValidationError(f"The {noun} could not be found. Please {again} again.")

    size = audio.stat().st_size
    if size == 0:
        if source == "upload":
            raise AudioValidationError(
                "The uploaded file is empty. Please choose a different .mp3."
            )
        if source == "file":
            raise AudioValidationError("The audio file is empty. Please send a different file.")
        raise AudioValidationError("The recording is empty. Please record again.")
    if size > max_bytes:
        raise AudioValidationError(
            f"The {noun} is {_mb(size)} MB, which is over the {_mb(max_bytes)} MB limit. "
            "Please use a shorter recording."
        )

    if source == "recording" and _is_silent(audio):
        raise AudioValidationError(SILENT_RECORDING_MESSAGE)
    if source == "file" and audio.suffix.lower() == ".wav" and _is_silent(audio):
        raise AudioValidationError(SILENT_FILE_MESSAGE)

    return audio


def _is_silent(audio: Path) -> bool:
    """True if `audio` is a 16-bit PCM WAV (what Gradio's recorder writes) with no audible
    sample. Files that can't be read this way are let through for the provider to judge."""
    try:
        with wave.open(str(audio), "rb") as wav:
            if wav.getsampwidth() != 2:
                return False
            limit = SILENCE_PEAK * 32768
            while chunk := wav.readframes(65536):
                samples = array.array("h", chunk[: len(chunk) - len(chunk) % 2])
                if sys.byteorder == "big":
                    samples.byteswap()
                if samples and max(abs(min(samples)), max(samples)) >= limit:
                    return False
            return True
    except (wave.Error, EOFError) as exc:
        logger.info("Skipping silence check for unreadable WAV: %s", exc)
        return False


def _mb(n_bytes: int) -> str:
    return f"{n_bytes / (1024 * 1024):.1f}"
