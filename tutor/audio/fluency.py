"""Fluency measures from word timings: pauses between words and speaking rate.

`analyse`, `describe` and `summarise` are pure functions. `transcribe_with_fluency` is the
single entry point that combines a transcription call with the analysis for interfaces.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tutor.audio import transcriber
from tutor.audio.transcriber import Transcript, Word
from tutor.audio.validation import AudioSource
from tutor.core.config import Settings

# A silent gap of at least 250 ms between words is the usual threshold for a pause in
# second-language fluency research (shorter gaps are articulation, not hesitation).
PAUSE_THRESHOLD_S = 0.25
_EPSILON = 1e-9  # so a gap of exactly the threshold isn't lost to float rounding

UNAVAILABLE_MESSAGE = "Fluency measures unavailable for this recording."


@dataclass(frozen=True)
class Pause:
    after_word: str
    start: float
    duration: float


@dataclass(frozen=True)
class FluencyReport:
    word_count: int
    speaking_time_s: float
    words_per_minute: float
    pauses: tuple[Pause, ...]

    @property
    def pause_count(self) -> int:
        return len(self.pauses)

    @property
    def mean_pause_s(self) -> float:
        return sum(p.duration for p in self.pauses) / len(self.pauses) if self.pauses else 0.0

    @property
    def longest_pause_s(self) -> float:
        return max((p.duration for p in self.pauses), default=0.0)


def analyse(transcript: Transcript) -> FluencyReport | None:
    """Measure pauses and words per minute, or return `None` if there are too few timings.

    Fillers (« euh », « hum ») count as words, since they are spoken. Punctuation-only
    tokens are ignored. Speaking time runs from the first word's start to the last's end.
    """
    words = [w for w in transcript.words if _is_spoken(w)]
    if len(words) < 2:
        return None

    speaking_time = words[-1].end - words[0].start
    if speaking_time <= 0:
        return None

    pauses = tuple(
        Pause(after_word=prev.text, start=prev.end, duration=nxt.start - prev.end)
        for prev, nxt in zip(words, words[1:], strict=False)
        if nxt.start - prev.end >= PAUSE_THRESHOLD_S - _EPSILON
    )
    return FluencyReport(
        word_count=len(words),
        speaking_time_s=speaking_time,
        words_per_minute=len(words) / speaking_time * 60,
        pauses=pauses,
    )


def describe(report: FluencyReport) -> str:
    """A short plain-text summary, suitable for any interface."""
    lines = [
        f"Words: {report.word_count} · Speaking time: {report.speaking_time_s:.1f} s · "
        f"{report.words_per_minute:.0f} words/min",
    ]
    heading = f"Pauses ≥ {PAUSE_THRESHOLD_S:g} s: {report.pause_count}"
    if report.pauses:
        heading += f" · mean {report.mean_pause_s:.2f} s · longest {report.longest_pause_s:.2f} s"
    lines.append(heading)

    width = max((len(p.after_word) for p in report.pauses), default=0) + 2
    for p in report.pauses:
        quoted = f"“{p.after_word}”".ljust(width)
        lines.append(f"  after {quoted}  at {p.start:.1f} s  — {p.duration:.2f} s")
    return "\n".join(lines)


def summarise(transcript: Transcript) -> str:
    """`describe(analyse(transcript))`, or a clear message when timings are missing."""
    report = analyse(transcript)
    return describe(report) if report else UNAVAILABLE_MESSAGE


def transcribe_with_fluency(
    audio_path: str | Path,
    *,
    source: AudioSource = "upload",
    session: Any | None = None,
    settings: Settings | None = None,
) -> tuple[str, str]:
    """Transcribe to French and return `(french_text, fluency_summary)`."""
    transcript = transcriber.transcribe_detailed(
        audio_path, source=source, session=session, settings=settings
    )
    return transcript.text, summarise(transcript)


def _is_spoken(word: Word) -> bool:
    return any(ch.isalnum() for ch in word.text)
