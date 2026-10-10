"""Turns hosted-inference failures into user-safe `InferenceError`s, logging the detail."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from huggingface_hub.errors import HfHubHTTPError

from tutor.core.errors import InferenceError, TutorError

logger = logging.getLogger(__name__)


@contextmanager
def inference_errors(task: str) -> Iterator[None]:
    """Run a model call, converting any provider exception into an `InferenceError`.

    `task` is a short human-readable name ("transcription") used in messages and logs.
    """
    try:
        yield
    except TutorError:
        raise
    except HfHubHTTPError as exc:
        status = exc.response.status_code
        logger.error("%s failed with HTTP %s: %s", task, status, exc)
        raise InferenceError(_message_for_status(task, status)) from exc
    except Exception as exc:
        # huggingface_hub wraps some timeouts in InferenceTimeoutError (a TimeoutError), but
        # transport-level ones surface as httpx2.*Timeout* — match both without importing httpx2.
        if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
            logger.warning("%s timed out: %s", task, exc)
            raise InferenceError(
                f"The {task} service took too long to respond. "
                "Please try again, or upload a shorter recording."
            ) from exc
        logger.exception("%s failed unexpectedly", task)
        raise InferenceError(
            f"The {task} service is unavailable right now. Please try again in a moment."
        ) from exc


def _message_for_status(task: str, status: int) -> str:
    if status == 429:
        return f"The {task} service is receiving too many requests. Please wait a minute and retry."
    if status == 413:
        return "The recording is too large for the hosted model. Please upload a shorter clip."
    if status == 402:
        return "The Hugging Face account has run out of inference credits. Please try again later."
    if status in (401, 403):
        return "The Hugging Face token was rejected. Check that HF_TOKEN is valid."
    if status == 404:
        return f"The configured {task} model is not available from Hugging Face right now."
    if status in (502, 503, 504):
        return f"The {task} model is temporarily unavailable. Please try again shortly."
    return f"The {task} service returned an error. Please try again."
