import pytest
from huggingface_hub import TranslationOutput

from tests.conftest import FakeSession, http_error
from tutor.audio import translator
from tutor.core.errors import AudioValidationError, InferenceError


@pytest.mark.parametrize("source", ["upload", "recording"])
def test_translate_audio_reuses_transcribe(monkeypatch, client, settings, mp3, source):
    calls = []
    session = FakeSession()

    def fake_transcribe(path, *, source, session, settings):
        calls.append((path, source, session))
        return "Bonjour"

    monkeypatch.setattr(translator.transcriber, "transcribe", fake_transcribe)
    client.translation.return_value = TranslationOutput(translation_text="Hello")

    result = translator.translate_audio(
        mp3, source=source, session=session, client=client, settings=settings
    )

    assert result == "Hello"
    assert calls == [(mp3, source, session)]
    assert session.calls == []
    client.translation.assert_called_once_with("Bonjour", model="test/mt")


def test_full_pipeline_with_fakes(client, settings, wav):
    session = FakeSession(payload={"text": "Euh… merci beaucoup."})
    client.translation.return_value = TranslationOutput(translation_text=" Uh… thank you. ")

    result = translator.translate_audio(
        wav, source="recording", session=session, client=client, settings=settings
    )

    assert result == "Uh… thank you."
    client.translation.assert_called_once_with("Euh… merci beaucoup.", model="test/mt")


def test_invalid_upload_never_calls_api(client, settings, tmp_path):
    empty = tmp_path / "empty.mp3"
    empty.write_bytes(b"")
    session = FakeSession()

    with pytest.raises(AudioValidationError):
        translator.translate_audio(empty, session=session, client=client, settings=settings)
    assert session.calls == []
    client.translation.assert_not_called()


def test_translation_api_error_becomes_friendly(client, settings):
    client.translation.side_effect = http_error(429)

    with pytest.raises(InferenceError, match="translation service is receiving too many"):
        translator.translate_text("Bonjour", client=client, settings=settings)


def test_empty_translation_is_an_error(client, settings):
    client.translation.return_value = TranslationOutput(translation_text="")

    with pytest.raises(InferenceError, match="empty"):
        translator.translate_text("Bonjour", client=client, settings=settings)
