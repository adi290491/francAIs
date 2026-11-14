from unittest.mock import MagicMock

import gradio as gr
import pytest

from tutor.core.errors import AudioValidationError, InferenceError
from ui.app import build_demo
from ui.features.audio_tools import MIC_DEVICE_JS
from ui.handlers import (
    GENERIC_ERROR_MESSAGE,
    RECORD_MODE,
    UPLOAD_MODE,
    audio_handler,
    clearing_fluency,
    pick_audio,
    toggle_inputs,
)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (UPLOAD_MODE, ("up.mp3", "upload")),
        (RECORD_MODE, ("audio.wav", "recording")),
    ],
)
def test_pick_audio_follows_mode(mode, expected):
    assert pick_audio(mode, "up.mp3", "audio.wav") == expected


def test_pick_audio_treats_blank_as_missing():
    assert pick_audio(RECORD_MODE, "up.mp3", "") == (None, "recording")


@pytest.mark.parametrize(
    ("mode", "upload", "recording", "message"),
    [
        (UPLOAD_MODE, None, "audio.wav", "upload an .mp3"),
        (UPLOAD_MODE, "", None, "upload an .mp3"),
        (RECORD_MODE, "up.mp3", None, "record some audio"),
    ],
)
def test_missing_input_warns_and_skips_call(mode, upload, recording, message):
    fn = MagicMock()

    with pytest.warns(UserWarning, match=message):
        result = audio_handler(fn)(mode, upload, recording)

    fn.assert_not_called()
    assert result == gr.skip()


def test_missing_input_skips_every_output():
    with pytest.warns(UserWarning):
        result = audio_handler(MagicMock(), n_outputs=2)(RECORD_MODE, None, None)

    assert result == (gr.skip(), gr.skip())


@pytest.mark.parametrize(
    ("mode", "path", "source"),
    [(UPLOAD_MODE, "up.mp3", "upload"), (RECORD_MODE, "audio.wav", "recording")],
)
def test_calls_fn_with_active_path_and_source(mode, path, source):
    fn = MagicMock(return_value="texte")

    assert audio_handler(fn)(mode, "up.mp3", "audio.wav") == "texte"
    fn.assert_called_once_with(path, source=source)


def test_transcribe_returns_both_outputs():
    fn = MagicMock(return_value=("Euh… bonjour", "Words: 2"))

    result = audio_handler(fn, n_outputs=2)(RECORD_MODE, None, "audio.wav")

    assert result == ("Euh… bonjour", "Words: 2")


def test_translate_clears_fluency():
    translate = MagicMock(return_value="Hello", __name__="translate")

    result = audio_handler(clearing_fluency(translate), n_outputs=2)(UPLOAD_MODE, "a.mp3", None)

    assert result == ("Hello", "")
    translate.assert_called_once_with("a.mp3", source="upload")


@pytest.mark.parametrize("error", [AudioValidationError("Only .mp3"), InferenceError("Busy")])
def test_tutor_errors_shown_verbatim(error):
    fn = MagicMock(side_effect=error)

    with pytest.raises(gr.Error) as excinfo:
        audio_handler(fn)(UPLOAD_MODE, "a.mp3", None)
    assert excinfo.value.message == str(error)


def test_unexpected_error_shows_generic_message():
    fn = MagicMock(side_effect=KeyError("secret detail"), __name__="fn")

    with pytest.raises(gr.Error) as excinfo:
        audio_handler(fn)(UPLOAD_MODE, "a.mp3", None)
    assert excinfo.value.message == GENERIC_ERROR_MESSAGE


@pytest.mark.parametrize(
    ("mode", "upload_visible", "recording_visible"),
    [(UPLOAD_MODE, True, False), (RECORD_MODE, False, True)],
)
def test_toggle_inputs_switches_visibility(mode, upload_visible, recording_visible):
    upload, recording = toggle_inputs(mode)

    assert upload["visible"] is upload_visible
    assert recording["visible"] is recording_visible


def test_build_demo_does_not_need_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    demo = build_demo()

    assert isinstance(demo, gr.Blocks)
    audios = [b for b in demo.blocks.values() if isinstance(b, gr.Audio)]
    assert sorted(tuple(a.sources) for a in audios) == [("microphone",), ("upload",)]


def test_mic_device_fix_is_loaded_on_page_load(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    demo = build_demo()

    load_js = [f.js for f in demo.fns.values() if f.js and "mic-select" in f.js]
    assert load_js == [MIC_DEVICE_JS]
    assert MIC_DEVICE_JS.lstrip().startswith("() =>")
    assert "deviceId: { exact: deviceId }" in MIC_DEVICE_JS
    assert '"devicechange"' in MIC_DEVICE_JS  # list refreshes when a mic connects later
    assert "waitForSignal" in MIC_DEVICE_JS  # recording starts only once the mic sends audio
