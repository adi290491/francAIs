"""The single place where the Hugging Face `InferenceClient` is created."""

from functools import lru_cache

from huggingface_hub import InferenceClient

from tutor.core.config import Settings, get_settings


def build_client(settings: Settings) -> InferenceClient:
    """Create an authenticated client for the given settings."""
    return InferenceClient(token=settings.hf_token, timeout=settings.inference_timeout_s)


@lru_cache(maxsize=1)
def get_client() -> InferenceClient:
    """Process-wide shared client, built from `get_settings()` on first use."""
    return build_client(get_settings())
