import pytest
from huggingface_hub import AutomaticSpeechRecognitionOutput, TranslationOutput

from tests.conftest import http_error
from tutor.audio import translator
from tutor.core.errors import AudioValidationError, InferenceError


def test_translate_audio_reuses_transcribe(monkeypatch, client, settings, mp3):
    calls = []

    def fake_transcribe(path, *, client, settings):
        calls.append(path)
        return "Bonjour"

    monkeypatch.setattr(translator.transcriber, "transcribe", fake_transcribe)
    client.translation.return_value = TranslationOutput(translation_text="Hello")

    assert translator.translate_audio(mp3, client=client, settings=settings) == "Hello"
    assert calls == [mp3]
    client.automatic_speech_recognition.assert_not_called()
    client.translation.assert_called_once_with("Bonjour", model="test/mt")


def test_full_pipeline_with_mocked_client(client, settings, mp3):
    client.automatic_speech_recognition.return_value = AutomaticSpeechRecognitionOutput(
        text="Merci beaucoup."
    )
    client.translation.return_value = TranslationOutput(translation_text=" Thank you very much. ")

    assert translator.translate_audio(mp3, client=client, settings=settings) == (
        "Thank you very much."
    )


def test_invalid_upload_never_calls_api(client, settings, tmp_path):
    empty = tmp_path / "empty.mp3"
    empty.write_bytes(b"")

    with pytest.raises(AudioValidationError):
        translator.translate_audio(empty, client=client, settings=settings)
    client.automatic_speech_recognition.assert_not_called()
    client.translation.assert_not_called()


def test_translation_api_error_becomes_friendly(client, settings):
    client.translation.side_effect = http_error(429)

    with pytest.raises(InferenceError, match="translation service is receiving too many"):
        translator.translate_text("Bonjour", client=client, settings=settings)


def test_empty_translation_is_an_error(client, settings):
    client.translation.return_value = TranslationOutput(translation_text="")

    with pytest.raises(InferenceError, match="empty"):
        translator.translate_text("Bonjour", client=client, settings=settings)
