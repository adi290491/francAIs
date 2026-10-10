"""Audio tools view: upload an .mp3, then transcribe it or translate it."""

from collections.abc import Callable

import gradio as gr

from tutor.audio.transcriber import transcribe
from tutor.audio.translator import translate_audio
from ui.handlers import audio_handler


def render(
    *,
    transcribe_fn: Callable[[str], str] = transcribe,
    translate_fn: Callable[[str], str] = translate_audio,
) -> None:
    """Draw the audio tools into the current `gr.Blocks` context.

    The service functions are injectable so the view can be reused or tested with fakes.
    """
    audio = gr.Audio(sources=["upload"], type="filepath", label="Upload French audio (.mp3)")
    with gr.Row():
        transcribe_btn = gr.Button("Transcribe (French)", variant="primary")
        translate_btn = gr.Button("Translate (English)", variant="primary")
    output = gr.Textbox(lines=12, label="Output", interactive=False, buttons=["copy"])

    transcribe_btn.click(audio_handler(transcribe_fn), inputs=audio, outputs=output)
    translate_btn.click(audio_handler(translate_fn), inputs=audio, outputs=output)
