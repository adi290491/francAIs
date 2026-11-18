"""v2_1: transcription and translation exposed as MCP tools."""

from unittest.mock import MagicMock

import gradio as gr
import pytest
from gradio.data_classes import FileData
from gradio.mcp import GradioMCPServer

from tutor.core.errors import AudioValidationError, InferenceError
from ui.app import build_demo
from ui.features import mcp_tools
from ui.handlers import GENERIC_ERROR_MESSAGE, NO_TOOL_FILE_MESSAGE, tool_handler

TOOLS = ["transcribe_french", "translate_to_english"]

# --- tool_handler ---


def test_tool_handler_passes_path_with_file_source():
    fn = MagicMock(return_value="texte")

    assert tool_handler(fn)("clip.wav") == "texte"
    fn.assert_called_once_with("clip.wav", source="file")


@pytest.mark.parametrize("path", [None, ""])
def test_tool_handler_missing_file_is_an_error(path):
    fn = MagicMock()

    with pytest.raises(gr.Error) as excinfo:
        tool_handler(fn)(path)
    assert excinfo.value.message == NO_TOOL_FILE_MESSAGE
    fn.assert_not_called()


@pytest.mark.parametrize("error", [AudioValidationError("Only .mp3"), InferenceError("Busy")])
def test_tool_handler_shows_tutor_errors_verbatim(error):
    with pytest.raises(gr.Error) as excinfo:
        tool_handler(MagicMock(side_effect=error))("a.mp3")
    assert excinfo.value.message == str(error)


def test_tool_handler_hides_unexpected_errors():
    fn = MagicMock(side_effect=KeyError("hf_secret"), __name__="fn")

    with pytest.raises(gr.Error) as excinfo:
        tool_handler(fn)("a.mp3")
    assert excinfo.value.message == GENERIC_ERROR_MESSAGE


# --- the tool functions ---


def _tools(transcribe_fn=None, translate_fn=None) -> dict:
    """Render the tools with fakes and return {api_name: function}."""
    with gr.Blocks() as demo:
        mcp_tools.render(
            transcribe_fn=transcribe_fn or MagicMock(), translate_fn=translate_fn or MagicMock()
        )
    return {f.api_name: f.fn for f in demo.fns.values()}


def test_transcribe_tool_returns_text_and_fluency():
    transcribe = MagicMock(return_value=("Euh… bonjour", "Words: 2"))
    tools = _tools(transcribe_fn=transcribe)

    result = tools["transcribe_french"](FileData(path="/tmp/clip.mp3"))

    assert result == {"french_text": "Euh… bonjour", "fluency": "Words: 2"}
    transcribe.assert_called_once_with("/tmp/clip.mp3", source="file")


def test_translate_tool_returns_english():
    translate = MagicMock(return_value="Hello")
    tools = _tools(translate_fn=translate)

    assert tools["translate_to_english"]("/tmp/clip.wav") == "Hello"
    translate.assert_called_once_with("/tmp/clip.wav", source="file")


def test_tool_reports_tutor_error():
    tools = _tools(transcribe_fn=MagicMock(side_effect=InferenceError("Busy")))

    with pytest.raises(gr.Error, match="Busy"):
        tools["transcribe_french"](FileData(path="/tmp/clip.mp3"))


# --- what the app exposes ---


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    return build_demo()


def test_mcp_server_lists_exactly_the_two_tools(demo):
    server = GradioMCPServer(demo)

    assert sorted(server.tool_to_endpoint) == TOOLS


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_takes_one_required_audio_file(demo, tool):
    server = GradioMCPServer(demo)

    schema, filedata_positions = server.get_input_schema(tool)

    assert list(schema["properties"]) == ["audio"]
    assert schema["required"] == ["audio"]
    assert filedata_positions  # Gradio downloads the URL it is given into a local file


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_has_a_description(demo, tool):
    server = GradioMCPServer(demo)
    block_fn = server.get_block_fn_from_endpoint_name(server.tool_to_endpoint[tool])

    description, parameters = server.get_fn_description(block_fn, tool)

    assert "French" in description
    assert ".mp3 or .wav" in parameters["audio"]


def test_button_endpoints_still_callable_but_not_documented(demo):
    public = demo.get_api_info()["named_endpoints"]
    callable_ = demo.get_api_info(all_endpoints=True)["named_endpoints"]

    assert sorted(public) == ["/transcribe_french", "/translate_to_english"]
    assert {"/transcribe", "/translate"} <= set(callable_)
