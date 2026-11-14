import pytest

from tests.conftest import FakeSession
from tests.sample_responses import HESITANT_RESPONSE, HESITANT_TEXT
from tutor.audio import fluency
from tutor.audio.fluency import (
    PAUSE_THRESHOLD_S,
    UNAVAILABLE_MESSAGE,
    analyse,
    describe,
    summarise,
    transcribe_with_fluency,
)
from tutor.audio.transcriber import Transcript, Word, transcribe_detailed


@pytest.fixture
def hesitant(settings, wav) -> Transcript:
    session = FakeSession(payload=HESITANT_RESPONSE)
    return transcribe_detailed(wav, source="recording", session=session, settings=settings)


def _transcript(*timings: tuple[float, float]) -> Transcript:
    words = tuple(Word(f"w{i}", start, end) for i, (start, end) in enumerate(timings))
    return Transcript(text="x", words=words)


def test_pauses_detected_from_step0_timings(hesitant):
    report = analyse(hesitant)

    assert report is not None
    assert [p.after_word for p in report.pauses] == ["alors…", "hum.", "plaît,"]
    assert [round(p.duration, 2) for p in report.pauses] == [0.90, 1.32, 0.69]
    assert report.pause_count == 3
    assert report.longest_pause_s == pytest.approx(1.32)
    assert report.mean_pause_s == pytest.approx((0.90 + 1.32 + 0.69) / 3)


def test_words_per_minute(hesitant):
    report = analyse(hesitant)

    assert report.word_count == 12  # fillers count; " s" + "'il" is one word
    assert report.speaking_time_s == pytest.approx(7.8)
    assert report.words_per_minute == pytest.approx(12 / 7.8 * 60)


def test_gap_at_threshold_counts_but_just_below_does_not():
    at = _transcript((0.0, 1.0), (1.0 + PAUSE_THRESHOLD_S, 2.0))
    below = _transcript((0.0, 1.0), (1.0 + PAUSE_THRESHOLD_S - 0.01, 2.0))

    assert analyse(at).pause_count == 1
    assert analyse(below).pause_count == 0


def test_contiguous_words_have_no_pauses():
    report = analyse(_transcript((0.0, 0.5), (0.5, 1.0), (1.0, 1.5)))

    assert report.pauses == ()
    assert report.mean_pause_s == 0.0
    assert report.longest_pause_s == 0.0


@pytest.mark.parametrize("timings", [(), ((0.0, 0.5),), ((1.0, 1.0), (1.0, 1.0))])
def test_too_few_timings_gives_none(timings):
    assert analyse(_transcript(*timings)) is None


def test_punctuation_only_tokens_are_ignored():
    transcript = Transcript(
        text="x", words=(Word("oui", 0.0, 0.3), Word("…", 0.3, 0.9), Word("non", 1.0, 1.3))
    )

    report = analyse(transcript)

    assert report.word_count == 2
    assert [p.after_word for p in report.pauses] == ["oui"]


def test_describe_lists_summary_and_each_pause(hesitant):
    text = describe(analyse(hesitant))

    lines = text.splitlines()
    assert lines[0] == "Words: 12 · Speaking time: 7.8 s · 92 words/min"
    assert lines[1] == "Pauses ≥ 0.25 s: 3 · mean 0.97 s · longest 1.32 s"
    assert "“hum.”" in lines[3] and "at 3.6 s" in lines[3] and "1.32 s" in lines[3]
    assert len(lines) == 5


def test_describe_without_pauses_omits_mean():
    text = describe(analyse(_transcript((0.0, 0.5), (0.5, 1.0))))

    assert text.splitlines()[1] == "Pauses ≥ 0.25 s: 0"


def test_summarise_without_timings_says_unavailable():
    assert summarise(Transcript(text="Bonjour")) == UNAVAILABLE_MESSAGE


def test_transcribe_with_fluency_returns_text_and_summary(monkeypatch, hesitant, settings):
    calls = []

    def fake_detailed(path, *, source, session, settings):
        calls.append((path, source))
        return hesitant

    monkeypatch.setattr(fluency.transcriber, "transcribe_detailed", fake_detailed)

    text, summary = transcribe_with_fluency("audio.wav", source="recording", settings=settings)

    assert text == HESITANT_TEXT
    assert summary.startswith("Words: 12")
    assert calls == [("audio.wav", "recording")]
