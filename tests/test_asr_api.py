from dataclasses import replace

import pytest
from huggingface_hub.errors import HfHubHTTPError

from tests.conftest import FAKE_TOKEN, FakeSession
from tutor.core.asr_api import FILLER_PROMPT, request_transcription

ASR_URL = "https://asr.test/v1/audio/transcriptions"


@pytest.fixture
def asr_settings(settings):
    return replace(settings, asr_url=ASR_URL, inference_timeout_s=42.0)


def test_request_carries_every_field(asr_settings, mp3):
    session = FakeSession(payload={"text": "Salut", "words": []})

    result = request_transcription(mp3, settings=asr_settings, session=session)

    assert result == {"text": "Salut", "words": []}
    url, kwargs = session.calls[0]
    assert url == ASR_URL
    assert kwargs["data"] == {
        "model": "test/asr",
        "language": "fr",
        "temperature": "0",
        "prompt": FILLER_PROMPT,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "word",
    }
    assert kwargs["headers"] == {"Authorization": f"Bearer {FAKE_TOKEN}"}
    assert kwargs["timeout"] == 42.0


def test_filler_prompt_contains_fillers():
    assert "Euh" in FILLER_PROMPT
    assert "hum" in FILLER_PROMPT


@pytest.mark.parametrize(("name", "mime"), [("clip.mp3", "audio/mpeg"), ("audio.WAV", "audio/wav")])
def test_file_sent_with_mime_type(asr_settings, tmp_path, name, mime):
    path = tmp_path / name
    path.write_bytes(b"audio-bytes")
    session = FakeSession()

    request_transcription(path, settings=asr_settings, session=session)

    assert session.calls[0][1]["files"]["file"] == (name, b"audio-bytes", mime)


@pytest.mark.parametrize("status", [401, 413, 429, 503])
def test_http_error_raises_hf_error(asr_settings, mp3, status):
    session = FakeSession(status=status, payload={"error": "nope"})

    with pytest.raises(HfHubHTTPError) as excinfo:
        request_transcription(mp3, settings=asr_settings, session=session)
    assert excinfo.value.response.status_code == status
