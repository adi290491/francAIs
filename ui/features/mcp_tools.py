"""MCP tools: transcription and translation for MCP hosts (Claude, local clients).

Gradio's MCP server (`demo.launch(mcp_server=True)`) turns every public API endpoint into a
tool, named after the function and described by its docstring. These two endpoints have no
components; they take one audio file and reuse the same `tutor` functions as the buttons.
"""

from collections.abc import Callable

import gradio as gr
from gradio.data_classes import FileData

from tutor.audio.fluency import transcribe_with_fluency
from tutor.audio.translator import translate_audio
from ui.handlers import tool_handler


def render(
    *,
    transcribe_fn: Callable[..., tuple[str, str]] = transcribe_with_fluency,
    translate_fn: Callable[..., str] = translate_audio,
) -> None:
    """Register the MCP tool endpoints in the current `gr.Blocks` context.

    `transcribe_fn` and `translate_fn` have the same contract as in `audio_tools.render`.
    """
    run_transcribe = tool_handler(transcribe_fn)
    run_translate = tool_handler(translate_fn)

    def transcribe_french(audio: FileData) -> dict[str, str]:
        """Transcribe French speech to French text, keeping fillers (« euh », « hum »),
        and measure fluency (pauses and words per minute).

        Args:
            audio: French speech as an .mp3 or .wav file (25 MB max by default), given as a public http(s) URL or a URL returned by an upload tool.

        Returns:
            A JSON object: french_text (the verbatim French transcript) and fluency
            (words per minute and the pauses of 0.25 s or more between words).
        """  # noqa: E501 (Gradio reads an argument's description from one line)
        text, fluency = run_transcribe(_path(audio))
        return {"french_text": text, "fluency": fluency}

    def translate_to_english(audio: FileData) -> str:
        """Translate French speech to English text (transcribes it to French first).

        Args:
            audio: French speech as an .mp3 or .wav file (25 MB max by default), given as a public http(s) URL or a URL returned by an upload tool.

        Returns:
            The English translation.
        """  # noqa: E501
        return run_translate(_path(audio))

    gr.api(transcribe_french, api_name="transcribe_french")
    gr.api(translate_to_english, api_name="translate_to_english")


def _path(audio: FileData | str | None) -> str | None:
    """The local path of the file Gradio downloaded for the call."""
    if isinstance(audio, FileData):
        return audio.path
    return audio
