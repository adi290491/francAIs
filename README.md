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

Personal French tutoring assistant. Upload a French `.mp3` to transcribe it to French text or
translate it to English, using models served by Hugging Face Inference Providers.

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
