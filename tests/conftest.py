from unittest.mock import MagicMock

import pytest
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

from tutor.core.config import Settings

FAKE_TOKEN = "hf_fake_token_for_tests"


@pytest.fixture
def settings() -> Settings:
    return Settings(hf_token=FAKE_TOKEN, asr_model="test/asr", translation_model="test/mt")


@pytest.fixture
def client() -> MagicMock:
    """A mocked InferenceClient; tests never touch the network."""
    return MagicMock(spec=InferenceClient)


@pytest.fixture
def mp3(tmp_path):
    """A small stub .mp3 file (content is irrelevant because the client is mocked)."""
    path = tmp_path / "clip.mp3"
    path.write_bytes(b"ID3" + b"\x00" * 64)
    return path


def http_error(status: int) -> HfHubHTTPError:
    response = MagicMock(status_code=status, headers={})
    return HfHubHTTPError(f"{status} error from provider", response=response)
