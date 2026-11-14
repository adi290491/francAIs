"""Adapters between `tutor` functions and Gradio events.

This is the only place where `TutorError`s become `gr.Error` popups, so feature views
stay declarative and the business logic stays framework-free.
"""

import logging
from collections.abc import Callable
from typing import Any

import gradio as gr

from tutor.audio.validation import AudioSource
from tutor.core.errors import TutorError

logger = logging.getLogger(__name__)

UPLOAD_MODE = "Upload"
RECORD_MODE = "Record"
MODES = (UPLOAD_MODE, RECORD_MODE)

NO_FILE_MESSAGES: dict[AudioSource, str] = {
    "upload": "Please upload an .mp3 file first.",
    "recording": "Please record some audio first.",
}
GENERIC_ERROR_MESSAGE = "Something went wrong. Please try again."


def pick_audio(
    mode: str, upload_path: str | None, recording_path: str | None
) -> tuple[str | None, AudioSource]:
    """Return the active input's path (or `None` if it is empty) and its source."""
    if mode == RECORD_MODE:
        return recording_path or None, "recording"
    return upload_path or None, "upload"


def toggle_inputs(mode: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Visibility updates for (upload input, microphone input). Values are kept when hidden."""
    return gr.update(visible=mode != RECORD_MODE), gr.update(visible=mode == RECORD_MODE)


def audio_handler(
    fn: Callable[..., Any], *, n_outputs: int = 1
) -> Callable[[str, str | None, str | None], Any]:
    """Wrap `fn(audio_path, source=...)` as a handler taking `(mode, upload, recording)`.

    - Active input empty: show a mode-specific warning, leave outputs unchanged, skip the call.
    - `TutorError`: show its (user-safe) message.
    - Anything else: log it and show a generic message (no stack traces in the UI).
    """

    def handler(mode: str, upload_path: str | None, recording_path: str | None) -> Any:
        path, source = pick_audio(mode, upload_path, recording_path)
        if not path:
            gr.Warning(NO_FILE_MESSAGES[source])
            return gr.skip() if n_outputs == 1 else tuple(gr.skip() for _ in range(n_outputs))
        try:
            return fn(path, source=source)
        except TutorError as exc:
            raise gr.Error(str(exc), print_exception=False) from None
        except Exception:
            logger.exception("Unhandled error in %s", getattr(fn, "__name__", fn))
            raise gr.Error(GENERIC_ERROR_MESSAGE, print_exception=False) from None

    return handler


def clearing_fluency(fn: Callable[..., str]) -> Callable[..., tuple[str, str]]:
    """Adapt `fn -> text` to `(text, "")`, so a result never sits beside stale fluency figures."""

    def wrapped(audio_path: str, *, source: AudioSource) -> tuple[str, str]:
        return fn(audio_path, source=source), ""

    wrapped.__name__ = getattr(fn, "__name__", "wrapped")
    return wrapped
