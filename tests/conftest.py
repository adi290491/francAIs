from unittest.mock import MagicMock

import httpx2
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


class FakeSession:
    """Stands in for the HTTP session used by `asr_api`; never touches the network.

    Records each request and returns `payload` with `status`, or raises `exc` if given.
    """

    def __init__(self, status: int = 200, payload=None, exc: Exception | None = None):
        self.status = status
        self.payload = payload if payload is not None else {"text": "Bonjour", "words": []}
        self.exc = exc
        self.calls: list[tuple[str, dict]] = []

    def post(self, url, **kwargs):
        # Read the file now: the handle is closed once request_transcription returns.
        name, fh, mime = kwargs["files"]["file"]
        kwargs["files"] = {"file": (name, fh.read(), mime)}
        self.calls.append((url, kwargs))
        if self.exc is not None:
            raise self.exc
        return httpx2.Response(self.status, json=self.payload, request=httpx2.Request("POST", url))


@pytest.fixture
def wav(tmp_path):
    """A stub microphone recording, named the way Gradio names it."""
    path = tmp_path / "audio.wav"
    path.write_bytes(b"RIFF" + b"\x00" * 64)
    return path
