"""Audio tools view: upload an .mp3 or record from a microphone, then transcribe or translate."""

from collections.abc import Callable
from pathlib import Path

import gradio as gr

from tutor.audio.fluency import transcribe_with_fluency
from tutor.audio.translator import translate_audio
from ui.handlers import MODES, UPLOAD_MODE, audio_handler, clearing_fluency, toggle_inputs

# Browser-side fix so the recorder uses the microphone picked in its device dropdown (Gradio
# 6.30 ignores that choice). Run it once per page with `demo.load(None, js=MIC_DEVICE_JS)`.
MIC_DEVICE_JS = (Path(__file__).parent / "mic_device.js").read_text(encoding="utf-8")


def render(
    *,
    transcribe_fn: Callable[..., tuple[str, str]] = transcribe_with_fluency,
    translate_fn: Callable[..., str] = translate_audio,
) -> None:
    """Draw the audio tools into the current `gr.Blocks` context.

    `transcribe_fn(path, source=...)` returns `(french_text, fluency_summary)`;
    `translate_fn(path, source=...)` returns English text. Both are injectable so the view
    can be reused or tested with fakes.
    """
    mode = gr.Radio(list(MODES), value=UPLOAD_MODE, label="Input")
    upload = gr.Audio(sources=["upload"], type="filepath", label="Upload French audio (.mp3)")
    # The browser's recorder lists every available microphone (built-in, headset, phone).
    recording = gr.Audio(
        sources=["microphone"], type="filepath", label="Record French audio", visible=False
    )
    with gr.Row():
        transcribe_btn = gr.Button("Transcribe (French)", variant="primary")
        translate_btn = gr.Button("Translate (English)", variant="primary")
    output = gr.Textbox(lines=12, label="Output", interactive=False, buttons=["copy"])
    fluency = gr.Textbox(lines=8, label="Fluency (pauses & pace)", interactive=False)

    mode.change(toggle_inputs, inputs=mode, outputs=[upload, recording], api_visibility="private")
    inputs = [mode, upload, recording]
    transcribe_btn.click(
        audio_handler(transcribe_fn, n_outputs=2),
        inputs=inputs,
        outputs=[output, fluency],
        api_name="transcribe",
    )
    translate_btn.click(
        audio_handler(clearing_fluency(translate_fn), n_outputs=2),
        inputs=inputs,
        outputs=[output, fluency],
        api_name="translate",
    )
