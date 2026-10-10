"""Application settings, read from environment variables (and `.env` in local development)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

from tutor.core.errors import ConfigError

DEFAULT_ASR_MODEL = "openai/whisper-large-v3"
DEFAULT_TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-fr-en"
DEFAULT_MAX_UPLOAD_MB = 25.0
DEFAULT_INFERENCE_TIMEOUT_S = 120.0

MISSING_TOKEN_MESSAGE = (
    "HF_TOKEN is not set. For local runs, copy .env.example to .env and set "
    "HF_TOKEN=<your Hugging Face access token>. On Hugging Face Spaces, add a secret "
    "named HF_TOKEN in the Space settings."
)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration. The token is excluded from `repr` so it never ends up in logs."""

    hf_token: str = field(repr=False)
    asr_model: str = DEFAULT_ASR_MODEL
    translation_model: str = DEFAULT_TRANSLATION_MODEL
    max_upload_mb: float = DEFAULT_MAX_UPLOAD_MB
    inference_timeout_s: float = DEFAULT_INFERENCE_TIMEOUT_S

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build `Settings` from `env` (defaults to the process environment plus `.env`).

    Raises `ConfigError` if `HF_TOKEN` is missing or a numeric setting is invalid.
    """
    if env is None:
        load_dotenv()
        env = os.environ

    token = env.get("HF_TOKEN", "").strip()
    if not token:
        raise ConfigError(MISSING_TOKEN_MESSAGE)

    return Settings(
        hf_token=token,
        asr_model=env.get("ASR_MODEL", "").strip() or DEFAULT_ASR_MODEL,
        translation_model=env.get("TRANSLATION_MODEL", "").strip() or DEFAULT_TRANSLATION_MODEL,
        max_upload_mb=_positive_float(env, "MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB),
        inference_timeout_s=_positive_float(
            env, "INFERENCE_TIMEOUT_S", DEFAULT_INFERENCE_TIMEOUT_S
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, loaded once on first use."""
    return load_settings()


def _positive_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from None
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0, got {raw!r}.")
    return value
