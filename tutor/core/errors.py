"""Error types raised by the tutor package.

The message of every `TutorError` is written for end users: it must never contain
tokens, stack traces or raw provider responses. Technical detail goes to the log.
"""


class TutorError(Exception):
    """Base class for errors whose message is safe to show to the user."""


class ConfigError(TutorError):
    """Required configuration is missing or invalid."""


class AudioValidationError(TutorError):
    """The uploaded audio file was rejected before any model call."""


class InferenceError(TutorError):
    """A hosted model call failed (timeout, rate limit, provider error, ...)."""
