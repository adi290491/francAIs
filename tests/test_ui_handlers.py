from unittest.mock import MagicMock

import gradio as gr
import pytest

from tutor.core.errors import AudioValidationError, InferenceError
from ui.app import build_demo
from ui.handlers import GENERIC_ERROR_MESSAGE, audio_handler


@pytest.mark.parametrize("missing", [None, ""])
def test_no_file_warns_and_skips_call(missing):
    fn = MagicMock()

    with pytest.warns(UserWarning, match="upload an .mp3"):
        result = audio_handler(fn)(missing)

    fn.assert_not_called()
    assert result == gr.skip()


def test_success_returns_text():
    assert audio_handler(lambda path: f"text for {path}")("a.mp3") == "text for a.mp3"


@pytest.mark.parametrize("error", [AudioValidationError("Only .mp3"), InferenceError("Busy")])
def test_tutor_errors_shown_verbatim(error):
    fn = MagicMock(side_effect=error)

    with pytest.raises(gr.Error) as excinfo:
        audio_handler(fn)("a.mp3")
    assert excinfo.value.message == str(error)


def test_unexpected_error_shows_generic_message():
    fn = MagicMock(side_effect=KeyError("secret detail"), __name__="fn")

    with pytest.raises(gr.Error) as excinfo:
        audio_handler(fn)("a.mp3")
    assert excinfo.value.message == GENERIC_ERROR_MESSAGE


def test_build_demo_does_not_need_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    assert isinstance(build_demo(), gr.Blocks)
