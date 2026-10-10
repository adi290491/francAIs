"""Adapters between `tutor` functions and Gradio events.

This is the only place where `TutorError`s become `gr.Error` popups, so feature views
stay declarative and the business logic stays framework-free.
"""

import logging
from collections.abc import Callable
from typing import Any

import gradio as gr

from tutor.core.errors import TutorError

logger = logging.getLogger(__name__)

NO_FILE_MESSAGE = "Please upload an .mp3 file first."
GENERIC_ERROR_MESSAGE = "Something went wrong. Please try again."


def audio_handler(fn: Callable[[str], str]) -> Callable[[str | None], Any]:
    """Wrap `fn(audio_path) -> str` as a Gradio handler for a filepath `gr.Audio` input.

    - No file uploaded: show a warning, leave the output unchanged, skip the call.
    - `TutorError`: show its (user-safe) message.
    - Anything else: log it and show a generic message (no stack traces in the UI).
    """

    def handler(audio_path: str | None) -> Any:
        if not audio_path:
            gr.Warning(NO_FILE_MESSAGE)
            return gr.skip()
        try:
            return fn(audio_path)
        except TutorError as exc:
            raise gr.Error(str(exc), print_exception=False) from None
        except Exception:
            logger.exception("Unhandled error in %s", getattr(fn, "__name__", fn))
            raise gr.Error(GENERIC_ERROR_MESSAGE, print_exception=False) from None

    return handler
