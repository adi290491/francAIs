---
title: French Tutor
emoji: 🥐
colorFrom: blue
colorTo: red
sdk: gradio
sdk_version: 6.30.0
python_version: "3.10"
app_file: app.py
pinned: false
---

# francAIs

Personal French tutoring assistant. Upload a French `.mp3`, or switch to **Record** and speak
into any microphone your browser offers, then:

- **Transcribe (French)**: a literal French transcript (Whisper forced to French at temperature 0,
  keeping fillers such as « euh » and « hum »), plus a **Fluency** panel with words per minute and
  every pause of 0.25 s or more between words.
- **Translate (English)**: the transcript translated to English.

Models are served by Hugging Face Inference Providers: `openai/whisper-large-v3` on DeepInfra
(called through the HF router for word-level timestamps) and `Helsinki-NLP/opus-mt-fr-en`.
See [docs/STATUS.md](docs/STATUS.md) for what is built and its known limits.

## Run locally

```bash
uv sync
cp .env.example .env   # then set HF_TOKEN
uv run python app.py   # http://127.0.0.1:7860
```

## Develop

```bash
uv run pytest
uv run ruff check . && uv run ruff format .
```

After changing dependencies, regenerate the file the Space installs from:

```bash
uv export --no-hashes --no-dev --format requirements-txt > requirements.txt
```
