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

## v2 scope (build exactly this)
1. **Microphone recording** - accepts recording using available microphone options (system, phone, etc).
2. **Toggler** - toggles between v1 upload mode and recording mode.
3. **Transcribe button** - the transcribe button from v1 transcribes the recorded audio to French text. Force whisper to French text even on a hesitant recording.
4. **Translate button** — translates the recorded audio to English text.
5. **Fillers** - Keep the fillers from the recordings so passing a prompt like « Euh, alors… je, je voudrais… hum » keeps them instead of deleting.
6. **Word-level timestamp** - Maintain any gaps between words allowing pause lengths and words per minute, real fluency measures.
7. **temperature** - set to zero (0) for consistent, literal output.

Out of scope for v1: user accounts, saving history, any database, multiple languages other than French→English, streaming output.

## Tech stack

- **Python 3.10+** (the HF Gradio Space builds on 3.10 regardless of `python_version`, so the lock must resolve for 3.10)
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
│   │   ├── config.py       # Settings dataclass from env vars: HF_TOKEN, model IDs, ASR_URL, limits
│   │   ├── client.py       # The single shared InferenceClient factory (translation)
│   │   ├── asr_api.py      # The one direct HTTP call: DeepInfra Whisper with word timings
│   │   ├── errors.py       # TutorError hierarchy (user-safe messages)
│   │   └── inference.py    # Maps provider exceptions (timeout/429/413/…) to TutorError
│   └── audio/              # Feature: audio tools
│       ├── validation.py   # Validation by source: upload (.mp3) / recording (.wav); size, non-empty
│       ├── transcriber.py  # transcribe_detailed(path) -> Transcript(text, words, duration);
│       │                   #   transcribe(path) -> str  (French text)
│       ├── fluency.py      # analyse/describe: pauses & words per minute; transcribe_with_fluency()
│       └── translator.py   # translate_audio(path) -> str  (English text)
├── ui/                     # Gradio presentation layer. Depends on tutor, not vice versa.
│   ├── app.py              # build_demo(): composes feature views into one Blocks app
│   ├── handlers.py         # Adapts tutor functions to Gradio (TutorError -> gr.Error, etc.)
│   └── features/
│       └── audio_tools.py  # render(): mode toggle, upload + mic, buttons, Output + Fluency
├── tests/
│   ├── conftest.py         # settings/client fixtures, FakeSession for the ASR HTTP call
│   ├── sample_responses.py # a DeepInfra-shaped hesitant-French response
│   ├── test_config.py
│   ├── test_asr_api.py
│   ├── test_audio.py
│   ├── test_transcriber.py
│   ├── test_fluency.py
│   ├── test_translator.py
│   └── test_ui_handlers.py
├── docs/
│   ├── PLAN.md             # v2 implementation plan (incl. the step 0 provider check)
│   └── STATUS.md           # status of every v1/v2 scope item
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
- `tutor/` functions take `client` (or `session`, for the ASR HTTP call) and `settings` as optional keyword arguments (defaulting to the shared ones). Tests inject fakes instead of patching globals.
- `tutor/` raises `TutorError` subclasses whose message is safe to show users; `ui/handlers.py` is the only place that turns them into `gr.Error` / `gr.Warning`.
- Create one shared `InferenceClient` in a single place (`tutor/core/client.py`) rather than in every module. The only model call outside it is the ASR request in `tutor/core/asr_api.py` (see below).
- Adding a feature: new sub-package under `tutor/` (e.g. `tutor/vocabulary/`), a new `ui/features/<name>.py` with a `render()` function, and one line in `ui/app.py` to include it (e.g. inside a new `gr.Tab`).

## Model calls (Hugging Face Inference API)

Use `huggingface_hub.InferenceClient`, authenticated with `HF_TOKEN`.

**Transcription (v2)** — a direct `POST` to DeepInfra's OpenAI-compatible endpoint through the HF router, in `tutor/core/asr_api.py`. This is a deliberate, approved exception to "use `InferenceClient`": the v2 step 0 check (see `docs/PLAN.md`) found that `InferenceClient.automatic_speech_recognition` drops word timings for every provider, and hf-inference folds silences into words, so no client route gives real pause lengths.
- URL: `ASR_URL`, default `https://router.huggingface.co/deepinfra/v1/openai/audio/transcriptions`. Auth: `Authorization: Bearer HF_TOKEN` (billed to the same HF credits).
- `multipart/form-data`: `file`, `model=ASR_MODEL` (default `openai/whisper-large-v3`), `language=fr`, `temperature=0`, `prompt="Euh, alors… je, je voudrais… hum"` (keeps fillers), `response_format=verbose_json`, `timestamp_granularities[]=word`.
- Uses `huggingface_hub.utils.get_session()` and `hf_raise_for_status()`, so HTTP errors surface as `HfHubHTTPError` and `inference_errors` maps them like any other call. No new dependency.
- Response: `text`, `duration`, `words: [{word, start, end}]`. Split fragments (`" s"` + `"'il"`) are joined into one word.

**Fluency** — `tutor/audio/fluency.py` turns word timings into words per minute (first word start → last word end) and pauses (gaps ≥ 0.25 s). Fillers count as words.

**Translation** — two-step pipeline for v1: transcribe the audio to French with the function above, then translate the French text to English. Use `client.translation(...)` with a French→English model (e.g. `Helsinki-NLP/opus-mt-fr-en`), or `client.chat_completion(...)` with an instruct model if the translation endpoint isn't available for that model.

Important:
- **Before hardcoding any model ID, verify it is currently served by HF Inference Providers** (check the model page's "Inference Providers" panel or make a test call). Provider availability changes. Tell me which models you verified.
- Make every model ID configurable through env vars (`ASR_MODEL`, `TRANSLATION_MODEL`, plus `ASR_URL` for the endpoint) with defaults in `config.py`.
- The translate flow should reuse `transcriber.transcribe()`, not duplicate the ASR call.

## Validation and error handling

- Uploads: reject anything that isn't `.mp3` (check the extension, case-insensitive) with a clear message. Recordings: Gradio's microphone recorder always uploads `audio.wav`, so recordings must be `.wav`. Don't set `format="mp3"` on `gr.Audio` (it needs ffmpeg on the Space).
- Reject empty files and files over a configurable size limit (`MAX_UPLOAD_MB`, default 25). Hosted inference has payload limits, so long recordings may fail — surface that clearly rather than crashing.
- Inference calls time out after `INFERENCE_TIMEOUT_S` seconds (default 120) so a stuck provider can't hang the UI.
- If `HF_TOKEN` is missing, fail at startup with a message that says exactly what to set.
- Wrap inference calls: on timeouts, rate limits (HTTP 429), or provider errors, show a friendly message in the UI with `gr.Error` / `gr.Warning`. Log the technical detail with the `logging` module; never show tokens or stack traces in the UI.
- If either button is clicked with no audio in the active mode, show a mode-specific warning ("Please upload an .mp3 file first." / "Please record some audio first.") instead of calling the API.

## UI spec (Gradio Blocks)

- Title: "French Tutor" with a one-line description.
- Mode toggle: `gr.Radio(["Upload", "Record"], value="Upload", label="Input")`. Changing it toggles `visible` on the two audio inputs; both keep their values.
- `gr.Audio(sources=["upload"], type="filepath", label="Upload French audio (.mp3)")` — gives the user playback of their file.
- `gr.Audio(sources=["microphone"], type="filepath", label="Record French audio", visible=False)` — the browser recorder offers every available microphone (built-in, headset, phone browser over the Space's HTTPS).
- Two buttons side by side: **Transcribe (French)** and **Translate (English)** (API names `/transcribe`, `/translate`). Both act on the active mode's audio.
- `gr.Textbox(lines=12, label="Output", interactive=False, buttons=["copy"])` (Gradio 6 replaced `show_copy_button` with `buttons`).
- `gr.Textbox(lines=8, label="Fluency (pauses & pace)", interactive=False)` — filled by Transcribe ("Fluency measures unavailable for this recording." when timings are missing) and cleared by Translate.
- While a request runs, the buttons should show progress (Gradio's default queue/progress is fine).
- `app.py` ends with `demo.launch()` and must not hardcode a host or port, so it works both locally and on Spaces.

## Hugging Face Space deployment

The repo is the Space's source. Deploy via GitHub Action:

1. `README.md` must begin with Space front matter:
   ```yaml
   ---
   title: French Tutor
   emoji: 🥐   # HF requires an Extended_Pictographic emoji; flag emoji are rejected
   colorFrom: blue
   colorTo: red
   sdk: gradio
   sdk_version: <match the Gradio version in uv.lock>
   python_version: "3.10"   # matches .python-version and the Space build image
   app_file: app.py
   pinned: false
   ---
   ```
2. Spaces install from `requirements.txt`, not uv. Regenerate it whenever dependencies change:
   `uv export --no-hashes --no-dev --format requirements-txt > requirements.txt`
   and commit it in the same commit as the `pyproject.toml` change.
   The Space installs `requirements.txt` together with its own extras (`gradio[oauth,mcp]==<sdk_version>`, `spaces`, `torch`) on Python 3.10, so check that the combination resolves before pushing (the pydantic cap in `[tool.uv] constraint-dependencies` exists for this reason):
   `uv venv /tmp/space-check --python 3.10 && VIRTUAL_ENV=/tmp/space-check uv pip install --dry-run -r requirements.txt "gradio[oauth,mcp]==<sdk_version>" spaces`
3. `.github/workflows/deploy-to-hf.yml` runs on push to `master` and force-pushes it to the `main` branch of `https://huggingface.co/spaces/<HF_USERNAME>/<SPACE_NAME>` (e.g. `git push --force <remote> master:main` — Spaces build from `main`), authenticated with a GitHub Actions secret `HF_TOKEN` (write-scoped). Put the username and Space name in workflow `env:` variables, not inline.
4. The Space needs its own secret `HF_TOKEN` (read/inference-scoped) set in the Space settings for the inference calls.
5. The Space runs on ZeroGPU (the only free hardware; CPU basic needs PRO). ZeroGPU refuses to start without a `@spaces.GPU` function, so `app.py` imports the preinstalled `spaces` package first (optional locally) and defines a never-called placeholder. Keep all real work on hosted inference; don't add GPU code or list `spaces` as a dependency.

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
- Create a `docs` folder and a new file in it named `STATUS.md` and add your final status for each scope. If any previous scope is not present, add the status of that scope too.