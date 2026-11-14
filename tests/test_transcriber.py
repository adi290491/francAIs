import httpx2
import pytest

from tests.conftest import FAKE_TOKEN, FakeSession
from tests.sample_responses import HESITANT_RESPONSE, HESITANT_TEXT
from tutor.audio.transcriber import Transcript, Word, transcribe, transcribe_detailed
from tutor.core.errors import AudioValidationError, InferenceError


def test_returns_stripped_text_using_configured_model(settings, mp3):
    session = FakeSession(payload={"text": "  Bonjour tout le monde.  "})

    assert transcribe(mp3, session=session, settings=settings) == "Bonjour tout le monde."
    assert session.calls[0][1]["data"]["model"] == "test/asr"


def test_detailed_parses_words_and_duration(settings, wav):
    session = FakeSession(payload=HESITANT_RESPONSE)

    result = transcribe_detailed(wav, source="recording", session=session, settings=settings)

    assert isinstance(result, Transcript)
    assert result.duration == 10.3
    assert result.words[0] == Word("Euh,", 0.0, 0.4)
    assert [w.text for w in result.words] == [
        "Euh,", "alors…", "je,", "je", "voudrais…", "hum.",
        "Un", "café,", "s'il", "vous", "plaît,", "euh.",
    ]  # fmt: skip


def test_fillers_are_returned_unchanged(settings, wav):
    session = FakeSession(payload=HESITANT_RESPONSE)

    text = transcribe(wav, source="recording", session=session, settings=settings)

    assert text == HESITANT_TEXT
    for filler in ("Euh", "hum", "euh", "je, je"):
        assert filler in text


def test_split_fragments_are_joined(settings, mp3):
    payload = {
        "text": "s'il vous",
        "words": [
            {"word": " s", "start": 1.0, "end": 1.1},
            {"word": "'il", "start": 1.1, "end": 1.3},
            {"word": " vous", "start": 1.4, "end": 1.6},
        ],
    }

    result = transcribe_detailed(mp3, session=FakeSession(payload=payload), settings=settings)

    assert result.words == (Word("s'il", 1.0, 1.3), Word("vous", 1.4, 1.6))


def test_words_without_leading_spaces_are_not_merged(settings, mp3):
    payload = {
        "text": "un deux",
        "words": [
            {"word": "un", "start": 0.0, "end": 0.3},
            {"word": "deux", "start": 0.5, "end": 0.8},
        ],
    }

    result = transcribe_detailed(mp3, session=FakeSession(payload=payload), settings=settings)

    assert [w.text for w in result.words] == ["un", "deux"]


@pytest.mark.parametrize("words", [None, "nope", []])
def test_missing_words_gives_empty_tuple(settings, mp3, words):
    payload = {"text": "Bonjour", "words": words}

    result = transcribe_detailed(mp3, session=FakeSession(payload=payload), settings=settings)

    assert result == Transcript(text="Bonjour", words=(), duration=None)


def test_malformed_word_entries_are_skipped(settings, mp3):
    payload = {
        "text": "Bonjour",
        "words": [
            "junk",
            {"word": " a", "start": "0", "end": 1.0},
            {"word": " b", "start": 0.0},
            {"word": " ", "start": 0.0, "end": 0.1},
            {"word": " c", "start": 2.0, "end": 1.0},
            {"word": " Bonjour", "start": 0.2, "end": 0.6},
        ],
    }

    result = transcribe_detailed(mp3, session=FakeSession(payload=payload), settings=settings)

    assert result.words == (Word("Bonjour", 0.2, 0.6),)


@pytest.mark.parametrize("payload", [{"text": " "}, {"text": None}, {}])
def test_empty_transcript_is_an_error(settings, mp3, payload):
    with pytest.raises(InferenceError, match="No speech"):
        transcribe(mp3, session=FakeSession(payload=payload), settings=settings)


def test_non_object_response_is_an_error(settings, mp3):
    with pytest.raises(InferenceError, match="unexpected response"):
        transcribe(mp3, session=FakeSession(payload=["text"]), settings=settings)


@pytest.mark.parametrize("source", ["upload", "recording"])
def test_invalid_audio_never_calls_api(settings, tmp_path, source):
    wrong = tmp_path / ("clip.wav" if source == "upload" else "clip.mp3")
    wrong.write_bytes(b"data")
    session = FakeSession()

    with pytest.raises(AudioValidationError):
        transcribe(wrong, source=source, session=session, settings=settings)
    assert session.calls == []


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
def test_http_errors_become_friendly(settings, mp3, status, expected):
    session = FakeSession(status=status, payload={"error": "provider detail"})

    with pytest.raises(InferenceError, match=expected) as excinfo:
        transcribe(mp3, session=session, settings=settings)
    assert FAKE_TOKEN not in str(excinfo.value)


@pytest.mark.parametrize("exc", [httpx2.ReadTimeout("timed out"), TimeoutError("slow")])
def test_timeout_becomes_friendly(settings, mp3, exc):
    with pytest.raises(InferenceError, match="took too long"):
        transcribe(mp3, session=FakeSession(exc=exc), settings=settings)


def test_unexpected_error_hides_details(settings, mp3):
    session = FakeSession(exc=RuntimeError("internal boom at 0xdead"))

    with pytest.raises(InferenceError) as excinfo:
        transcribe(mp3, session=session, settings=settings)
    assert "boom" not in str(excinfo.value)
