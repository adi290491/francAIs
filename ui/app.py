"""Composes the feature views into the single Gradio app."""

import gradio as gr

from ui.features import audio_tools

TITLE = "French Tutor"
DESCRIPTION = (
    "Upload a French .mp3 or record yourself speaking French, then transcribe it to French "
    "text (with pause and pace measures) or translate it to English."
)


def build_demo() -> gr.Blocks:
    """Build the Blocks app. New features add a `render()` call here (e.g. inside a `gr.Tab`)."""
    with gr.Blocks(title=TITLE) as demo:
        gr.Markdown(f"# {TITLE}\n{DESCRIPTION}")
        audio_tools.render()
        demo.load(None, js=audio_tools.MIC_DEVICE_JS, api_name=False)
    return demo
