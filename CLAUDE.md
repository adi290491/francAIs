# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# French Tutor (v1)

## Project overview

A personal French tutoring assistant. **Version 1** is a narrow audio tool: the user uploads a French `.mp3`, then either transcribes it to French text or translates it to English text. The app has a Gradio UI and is deployed to a Hugging Face Space.

Later versions will add tutoring features (vocabulary, quizzes, conversation practice). Keep v1 small, but keep the code modular enough that new features can be added as new modules and new UI tabs without rewriting what exists.

## v1 scope (build exactly this)

1. **File upload** — accepts `.mp3` files only.
2. **Transcribe button** — transcribes the uploaded audio to French text.
3. **Translate button** — translates the uploaded audio to English text.
4. **Output textarea** — one multi-line textbox that shows the result of whichever button was last pressed.
5. **Gradio UI** — single page, Gradio Blocks.
6. **Hugging Face deployment** — the app runs as a Gradio Space and redeploys automatically when `master` is pushed to GitHub.

Out of scope for v1: microphone recording, user accounts, saving history, any database, multiple languages other than French→English, streaming output.

## Tech stack

- **Python 3.11+**
- **uv** for dependency and environment management (`pyproject.toml` + `uv.lock` are the source of truth)
- **Gradio** 6.x (pinned to the latest stable in `pyproject.toml`) for the UI
- **huggingface_hub** `InferenceClient` for all model calls — no models run locally
- **python-dotenv** for loading `HF_TOKEN` in local development
- **pytest** for tests
- **ruff** for linting and formatting

Do not add other dependencies without asking first.

## Architecture

```
.
├── app.py                  # HF Space entry point only: load settings, build UI, launch.
├── tutor/                  # Business logic. Never imports gradio or ui.
│   ├── core/               # Shared infrastructure used by every feature
│   │   ├── config.py       # Settings dataclass from env vars: HF_TOKEN, model IDs, limits
│   │   ├── client.py       # The single shared InferenceClient factory
│   │   ├── errors.py       # TutorError hierarchy (user-safe messages)
│   │   └── inference.py    # Maps provider exceptions (timeout/429/413/…) to TutorError
│   └── audio/              # Feature: audio tools
│       ├── validation.py   # Upload validation (extension, size, non-empty)
│       ├── transcriber.py  # transcribe(path) -> str  (French text)
│       └── translator.py   # translate_audio(path) -> str  (English text)
├── ui/                     # Gradio presentation layer. Depends on tutor, not vice versa.
│   ├── app.py              # build_demo(): composes feature views into one Blocks app
│   ├── handlers.py         # Adapts tutor functions to Gradio (TutorError -> gr.Error, etc.)
│   └── features/
│       └── audio_tools.py  # render(): upload, buttons, output for the audio feature
├── tests/
│   ├── test_config.py
│   ├── test_audio.py
│   ├── test_transcriber.py
│   ├── test_translator.py
│   └── test_ui_handlers.py
├── .github/workflows/
│   └── deploy-to-hf.yml    # Syncs master to the HF Space
├── pyproject.toml
├── uv.lock
├── requirements.txt        # GENERATED from uv for the HF Space — never edit by hand
├── .env.example            # HF_TOKEN=  (no real values)
├── .gitignore              # must include .env and .venv/
└── README.md               # Must start with HF Space YAML front matter (see below)
```

Rules:
- Dependency direction is `app.py` → `ui/` → `tutor/`. `ui/` contains no API calls and no validation logic; `tutor/` has no Gradio imports, so it can be unit-tested and reused by future interfaces.
- `tutor/` functions take `client` and `settings` as optional keyword arguments (defaulting to the shared ones). Tests inject fakes instead of patching globals.
- `tutor/` raises `TutorError` subclasses whose message is safe to show users; `ui/handlers.py` is the only place that turns them into `gr.Error` / `gr.Warning`.
- Create one shared `InferenceClient` in a single place (`tutor/core/client.py`) rather than in every module.
- Adding a feature: new sub-package under `tutor/` (e.g. `tutor/vocabulary/`), a new `ui/features/<name>.py` with a `render()` function, and one line in `ui/app.py` to include it (e.g. inside a new `gr.Tab`).

## Model calls (Hugging Face Inference API)

Use `huggingface_hub.InferenceClient`, authenticated with `HF_TOKEN`.

**Transcription** — `client.automatic_speech_recognition(audio_path, model=ASR_MODEL)`.
Default `ASR_MODEL` to a Whisper model such as `openai/whisper-large-v3`. Return the `.text` field.

**Translation** — two-step pipeline for v1: transcribe the audio to French with the function above, then translate the French text to English. Use `client.translation(...)` with a French→English model (e.g. `Helsinki-NLP/opus-mt-fr-en`), or `client.chat_completion(...)` with an instruct model if the translation endpoint isn't available for that model.

Important:
- **Before hardcoding any model ID, verify it is currently served by HF Inference Providers** (check the model page's "Inference Providers" panel or make a test call). Provider availability changes. Tell me which models you verified.
- Make every model ID configurable through env vars (`ASR_MODEL`, `TRANSLATION_MODEL`) with defaults in `config.py`.
- The translate flow should reuse `transcriber.transcribe()`, not duplicate the ASR call.

## Validation and error handling

- Reject anything that isn't `.mp3` (check the extension, case-insensitive) with a clear message.
- Reject empty files and files over a configurable size limit (`MAX_UPLOAD_MB`, default 25). Hosted inference has payload limits, so long recordings may fail — surface that clearly rather than crashing.
- Inference calls time out after `INFERENCE_TIMEOUT_S` seconds (default 120) so a stuck provider can't hang the UI.
- If `HF_TOKEN` is missing, fail at startup with a message that says exactly what to set.
- Wrap inference calls: on timeouts, rate limits (HTTP 429), or provider errors, show a friendly message in the UI with `gr.Error` / `gr.Warning`. Log the technical detail with the `logging` module; never show tokens or stack traces in the UI.
- If either button is clicked with no file uploaded, show a warning instead of calling the API.

## UI spec (Gradio Blocks)

- Title: "French Tutor" with a one-line description.
- `gr.Audio(sources=["upload"], type="filepath", label="Upload French audio (.mp3)")` — gives the user playback of their file.
- Two buttons side by side: **Transcribe (French)** and **Translate (English)**.
- `gr.Textbox(lines=12, label="Output", interactive=False, buttons=["copy"])` (Gradio 6 replaced `show_copy_button` with `buttons`).
- While a request runs, the buttons should show progress (Gradio's default queue/progress is fine).
- `app.py` ends with `demo.launch()` and must not hardcode a host or port, so it works both locally and on Spaces.

## Hugging Face Space deployment

The repo is the Space's source. Deploy via GitHub Action:

1. `README.md` must begin with Space front matter:
   ```yaml
   ---
   title: French Tutor
   emoji: 🇫🇷
   colorFrom: blue
   colorTo: red
   sdk: gradio
   sdk_version: <match the Gradio version in uv.lock>
   app_file: app.py
   pinned: false
   ---
   ```
2. Spaces install from `requirements.txt`, not uv. Regenerate it whenever dependencies change:
   `uv export --no-hashes --no-dev --format requirements-txt > requirements.txt`
   and commit it in the same commit as the `pyproject.toml` change.
3. `.github/workflows/deploy-to-hf.yml` runs on push to `master` and force-pushes it to the `main` branch of `https://huggingface.co/spaces/<HF_USERNAME>/<SPACE_NAME>` (e.g. `git push --force <remote> master:main` — Spaces build from `main`), authenticated with a GitHub Actions secret `HF_TOKEN` (write-scoped). Put the username and Space name in workflow `env:` variables, not inline.
4. The Space needs its own secret `HF_TOKEN` (read/inference-scoped) set in the Space settings for the inference calls.

Manual steps I (the developer) will do — list them for me when you finish, don't attempt them: create the Space on huggingface.co, create the two tokens, and add the GitHub and Space secrets.

## Commands

```bash
uv sync                      # install deps
uv run python app.py         # run locally at http://127.0.0.1:7860
uv run pytest                # tests
uv run pytest tests/test_audio.py::test_name -v   # single test
uv run ruff check . && uv run ruff format .
uv add <pkg>                 # add a dependency (then regenerate requirements.txt)
```

## Testing

- Unit-test `tutor/` functions with the `InferenceClient` mocked. Tests must never call the real API or require `HF_TOKEN`.
- Cover: valid mp3, wrong extension, empty file, oversize file, API error → friendly error, translate reuses transcribe.
- Keep a tiny sample mp3 out of the repo; if a fixture is needed, generate a stub file in the test.

## Security

- Never commit `.env`, tokens, or real audio recordings.
- Never print or log `HF_TOKEN`.
- Uploaded files are processed and discarded; do not persist them.

## How to work in this repo

- Start by proposing a short plan and file list; wait for my OK before writing code.
- Build in this order, committing after each step works: project scaffold (uv, ruff, pytest) → `config.py` + `audio.py` with tests → `transcriber.py` with tests → `translator.py` with tests → `app.py` UI → README front matter + `requirements.txt` → deploy workflow.
- Run tests and ruff before saying a step is done.
- Use clear conventional commit messages (`feat:`, `fix:`, `chore:`, `test:`).
- Prefer simple, readable Python with type hints and short docstrings over clever abstractions.
- If something in this file conflicts with what you find (a model is unavailable, a Gradio API changed), stop and tell me rather than silently working around it.