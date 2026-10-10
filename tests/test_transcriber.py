import pytest
from huggingface_hub import AutomaticSpeechRecognitionOutput
from huggingface_hub.errors import InferenceTimeoutError

from tests.conftest import FAKE_TOKEN, http_error
from tutor.audio.transcriber import transcribe
from tutor.core.errors import AudioValidationError, InferenceError


def test_returns_stripped_text_using_configured_model(client, settings, mp3):
    client.automatic_speech_recognition.return_value = AutomaticSpeechRecognitionOutput(
        text="  Bonjour tout le monde.  "
    )

    assert transcribe(mp3, client=client, settings=settings) == "Bonjour tout le monde."
    client.automatic_speech_recognition.assert_called_once_with(str(mp3), model="test/asr")
    # Provider helpers such as fal-ai base64-encode anything that isn't a str, so a Path crashes.
    assert type(client.automatic_speech_recognition.call_args.args[0]) is str


def test_invalid_upload_never_calls_api(client, settings, tmp_path):
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"data")

    with pytest.raises(AudioValidationError):
        transcribe(wav, client=client, settings=settings)
    client.automatic_speech_recognition.assert_not_called()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, "too many requests"),
        (413, "too large"),
        (402, "out of inference credits"),
        (401, "token was rejected"),
        (404, "not available"),
        (503, "temporarily unavailable"),
        (500, "returned an error"),
    ],
)
def test_http_errors_become_friendly(client, settings, mp3, status, expected):
    client.automatic_speech_recognition.side_effect = http_error(status)

    with pytest.raises(InferenceError, match=expected) as excinfo:
        transcribe(mp3, client=client, settings=settings)
    assert FAKE_TOKEN not in str(excinfo.value)


def test_timeout_becomes_friendly(client, settings, mp3):
    client.automatic_speech_recognition.side_effect = InferenceTimeoutError("timed out")

    with pytest.raises(InferenceError, match="took too long"):
        transcribe(mp3, client=client, settings=settings)


def test_unexpected_error_hides_details(client, settings, mp3):
    client.automatic_speech_recognition.side_effect = RuntimeError("internal boom at 0xdead")

    with pytest.raises(InferenceError) as excinfo:
        transcribe(mp3, client=client, settings=settings)
    assert "boom" not in str(excinfo.value)


def test_empty_transcript_is_an_error(client, settings, mp3):
    client.automatic_speech_recognition.return_value = AutomaticSpeechRecognitionOutput(text=" ")

    with pytest.raises(InferenceError, match="No speech"):
        transcribe(mp3, client=client, settings=settings)
