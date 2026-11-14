# v2 implementation plan

This plan covers the v2 scope in [CLAUDE.md](../CLAUDE.md):

- microphone recording, with a toggle between upload and record modes
- forced-French transcription that keeps fillers
- English translation of recordings
- word-level timestamps for fluency measures (pause lengths, words per minute)
- temperature 0

## Step 0: provider check (done)

All three providers serving `openai/whisper-large-v3` were tested with a 10 s synthetic clip of hesitant French. The clip was a `.wav`, the format Gradio's microphone records. It had silences of 0.9 s, 1.2 s and 0.7 s inserted.

| Requirement | hf-inference | DeepInfra via `InferenceClient` | **DeepInfra direct** | fal-ai |
|---|---|---|---|---|
| Forced French | yes | yes | **yes** | yes |
| Fillers kept | yes (no prompt support) | yes | **yes** | no: dropped the first half of the sentence |
| Word timestamps | returned | dropped by the helper | **yes** | dropped by the helper |
| Real gaps between words | no: silences are folded into words | n/a | **yes: 0.90, 1.32, 0.69 s** | n/a |
| Temperature 0 | yes | yes | **yes** | not supported |

**Decision:** transcription calls DeepInfra's OpenAI-compatible endpoint directly through the HF router. Translation stays on `InferenceClient` with `Helsinki-NLP/opus-mt-fr-en`, as in v1.

The request is a `POST` to `https://router.huggingface.co/deepinfra/v1/openai/audio/transcriptions`. It is authenticated with `Bearer HF_TOKEN` and sent as `multipart/form-data` with these fields:

| Field | Value |
|---|---|
| `file` | the audio |
| `model` | `openai/whisper-large-v3` |
| `language` | `fr` |
| `temperature` | `0` |
| `prompt` | `Euh, alors… je, je voudrais… hum` |
| `response_format` | `verbose_json` |
| `timestamp_granularities[]` | `word` |

The response has `text`, `language`, `duration` and `words: [{word, start, end}]`.

Two further findings:

- **The prompt matters.** Without the filler prompt, the « euh » after « s'il vous plaît » was dropped.
- **Words can come back split.** For example, `" s"` is followed by `"'il"`, so word fragments must be joined before counting.

This is a deliberate exception to the CLAUDE.md rule that all model calls go through `InferenceClient`. It was approved because no provider returns usable word timings through the client.

## Design overview

```
ui/features/audio_tools.py   mode toggle, upload + mic inputs, Output + Fluency panels
ui/handlers.py               picks the active input by mode; TutorError -> gr.Error (unchanged role)
        │
tutor/audio/transcriber.py   transcribe_detailed() -> Transcript(text, words, duration)
                             transcribe() -> str  (thin wrapper, reused by translator)
tutor/audio/translator.py    translate_audio = transcribe + translate_text (unchanged flow)
tutor/audio/fluency.py       NEW: analyse(Transcript) -> FluencyReport; describe() -> str
tutor/audio/validation.py    allowed extensions depend on source (upload: .mp3, recording: .wav)
        │
tutor/core/asr_api.py        NEW: the one place that does the DeepInfra HTTP call
tutor/core/client.py         InferenceClient factory (translation only now)
tutor/core/inference.py      unchanged: maps HfHubHTTPError / timeouts to InferenceError
```

The dependency direction (`app.py` → `ui/` → `tutor/`) and the error-handling rules stay the same. No new dependencies: the HTTP call uses `huggingface_hub.utils.get_session()` and `hf_raise_for_status()`.

The steps are ordered so that each one depends only on earlier ones. Each step ends with `uv run pytest` and `uv run ruff check . && uv run ruff format .` passing, followed by one commit.

---

## Step 1: configuration and the transcription API call

**Files:** `tutor/core/config.py`, `tutor/core/asr_api.py` (new), `.env.example`, `tests/test_config.py`, `tests/test_asr_api.py` (new)

- **`config.py`:** add `asr_url: str`, defaulting to `DEFAULT_ASR_URL` (the router URL above) and overridable with the `ASR_URL` environment variable. `ASR_MODEL` keeps its default (`openai/whisper-large-v3`), which is DeepInfra's model ID too.
- **`asr_api.py`:** add `request_transcription(audio: Path, *, settings, session=None) -> dict`.
  - Builds the multipart fields from step 0. Language, temperature and prompt are module constants, because the spec fixes them.
  - Sets the MIME type from the extension: `.mp3` is `audio/mpeg`, `.wav` is `audio/wav`.
  - Uses `settings.inference_timeout_s` as the timeout.
  - Calls `hf_raise_for_status(response)`, so HTTP failures appear as `HfHubHTTPError` and the existing friendly messages for 429, 402, 401/403, 404, 413 and 5xx apply unchanged.
  - The token goes only in the `Authorization` header and is never logged.
  - `session` is injectable, so tests pass a fake and never touch the network.
- **`.env.example`:** add a commented `# ASR_URL=...` line.

**Tests:**
- The default and overridden `ASR_URL` are read correctly.
- The request carries every field (including `language`, `temperature`, `prompt` and `timestamp_granularities[]`), the bearer header, the right MIME type for `.mp3` and `.wav`, and the timeout.
- An HTTP error response raises `HfHubHTTPError`.

**Commit:** `feat: add DeepInfra transcription request with French, temperature 0, filler prompt and word timestamps`

## Step 2: validation by audio source

**Files:** `tutor/audio/validation.py`, `tests/test_audio.py`

- Add `AudioSource = Literal["upload", "recording"]` with these extension sets:

  | Source | Allowed extension |
  |---|---|
  | `upload` | `.mp3` (unchanged v1 rule) |
  | `recording` | `.wav` |

- Change the signature to `validate_audio(path, *, max_bytes, source="upload")`.
- The error message names what is accepted for that source, for example "Only .mp3 files are supported (got .ogg)." or "The recording must be a .wav file (got .webm)."
- Gradio's microphone output format will be confirmed from the installed Gradio source before this step is finished. If it is not `.wav`, the recording set changes to match. We will not add `format="mp3"`, because that needs ffmpeg on the Space.

**Tests:**
- All existing v1 cases still pass.
- A `.wav` recording is accepted, a `.wav` upload is rejected, and an `.mp3` recording is rejected.
- Empty and oversize recordings are rejected.

**Commit:** `feat: validate recordings (.wav) separately from uploads (.mp3)`

## Step 3: transcriber, fluency and translator

**Files:** `tutor/audio/transcriber.py`, `tutor/audio/fluency.py` (new), `tutor/audio/translator.py`, `tests/test_transcriber.py`, `tests/test_fluency.py` (new), `tests/test_translator.py`

### Transcriber

- **Data types:**
  - `Word(text: str, start: float, end: float)` (frozen dataclass)
  - `Transcript(text: str, words: tuple[Word, ...], duration: float | None)`
- **`transcribe_detailed(audio_path, *, source="upload", session=None, settings=None) -> Transcript`** does the following:
  1. Validates the file for its source.
  2. Calls `request_transcription` inside `inference_errors("transcription")`.
  3. Parses the response:
     - Strips the text. An empty text raises `InferenceError("No speech was detected…")`.
     - Joins word fragments: a fragment that doesn't start with whitespace is merged into the previous word (`" s"` + `"'il"` → `"s'il"`).
     - Skips malformed word entries rather than crashing.
  4. Returns the `Transcript`. A missing `words` list gives an empty tuple; it is not an error.
- **`transcribe(...) -> str`** returns `transcribe_detailed(...).text`, so v1 callers keep working.

### Fluency

`fluency.py` is pure functions with no I/O:

- **`PAUSE_THRESHOLD_S = 0.25`:** a gap of at least 0.25 s between consecutive words counts as a pause. This is the usual threshold for silent pauses in fluency research.
- **`analyse(transcript) -> FluencyReport | None`** returns `None` when there are fewer than two words. A `FluencyReport` holds:
  - `word_count`
  - `speaking_time_s`: from the first word's start to the last word's end
  - `words_per_minute`: `word_count / speaking_time_s * 60`
  - `pauses`: a list of `Pause(after_word, start, duration)`
  - `pause_count`, `mean_pause_s` and `longest_pause_s`
- **`describe(report) -> str`** returns a short plain-text summary for any interface, for example:

  ```
  Words: 18 · Speaking time: 10.3 s · 105 words/min
  Pauses ≥ 0.25 s: 3 · mean 0.97 s · longest 1.32 s
    after “alors…”   at 1.1 s  — 0.90 s
    after “hum.”     at 4.1 s  — 1.32 s
    after “euh.”     at 7.8 s  — 0.69 s
  ```

### Translator

- `translate_audio(audio_path, *, source="upload", session=None, client=None, settings=None)` still calls `transcriber.transcribe(...)` and then `translate_text(...)`.
- Only the parameters change: `session` is passed to the transcriber and `client` to the translation step.

### Tests

- **Transcriber:**
  - The parsed words match the step 0 response shape.
  - Fragments are joined.
  - Missing `words` gives an empty tuple.
  - Empty text raises an error.
  - Fillers in the response text are returned unchanged.
  - An HTTP error (429, 402, 5xx) or a timeout becomes a friendly `InferenceError`.
  - Validation runs before any network call.
- **Fluency:**
  - Pauses are detected from the step 0 timings (expect 3).
  - Words per minute is calculated correctly.
  - A gap just below the threshold is not counted as a pause.
  - Zero or one word gives `None`.
  - Contiguous timings (no gaps) give zero pauses.
- **Translator:**
  - It still reuses `transcribe`, and passes the source through.

**Commit:** `feat: word-level transcripts and fluency measures (pauses, words per minute)`

## Step 4: UI (mode toggle, microphone, fluency panel)

**Files:** `ui/features/audio_tools.py`, `ui/handlers.py`, `tests/test_ui_handlers.py`

### Layout

| Component | Details |
|---|---|
| Mode toggle | `gr.Radio(["Upload", "Record"], value="Upload", label="Input")` |
| Upload input | `gr.Audio(sources=["upload"], type="filepath", label="Upload French audio (.mp3)")`, unchanged from v1 |
| Microphone input | `gr.Audio(sources=["microphone"], type="filepath", label="Record French audio", visible=False)` |
| Buttons | **Transcribe (French)** and **Translate (English)**, unchanged |
| Output | the v1 `gr.Textbox`, unchanged |
| Fluency panel (new) | `gr.Textbox(lines=8, label="Fluency (pauses & pace)", interactive=False)` |

- Changing the mode toggles `visible` on the two audio inputs. Both keep their values, so switching back doesn't lose a clip.
- Microphone choice (system, external or phone) comes with Gradio's recorder, which uses the browser's `getUserMedia` and has a device picker. Phones work in their mobile browser because the Space is served over HTTPS; locally, `localhost` is allowed.

### Handlers

- `pick_audio(mode, upload_path, recording_path) -> (path, source)` chooses the active input. If it is empty, the handler shows a mode-specific `gr.Warning` ("Please upload an .mp3 file first." or "Please record some audio first.") and skips the call, as in v1.
- `audio_handler` is generalised to take `(mode, upload, recording)`. It calls `fn(path, source=...)` and returns its result. It is still the only place that turns errors into `gr.Error`.
- **Transcribe** calls a tutor function that returns `(transcript.text, fluency text)`. It fills both Output and Fluency. When timings are missing, Fluency says "Fluency measures unavailable for this recording."
- **Translate** fills Output with the English text and clears the Fluency panel, so stale figures from another clip never sit beside a translation.
- The service functions stay injectable through `render(...)`.

### Tests

- The upload or recording path is picked according to the mode.
- A missing file in either mode shows the right warning, makes no call and leaves the outputs unchanged.
- A `TutorError` becomes `gr.Error`.
- An unexpected exception becomes the generic message.
- Transcribe returns two outputs and Translate clears Fluency.

### Manual check

Run `uv run python app.py` and confirm:
- recording in the browser works
- switching modes works
- Transcribe fills both panels
- Translate gives English

This makes two or three real calls through the HF router, which uses a little inference credit. It also covers the one thing step 0 couldn't test: an `.mp3` upload through DeepInfra.

**Commit:** `feat: microphone recording mode with fluency panel`

## Step 5: docs and deployment check

**Files:** `CLAUDE.md`, `docs/STATUS.md` (new), `README.md`

- **CLAUDE.md:**
  - Update the architecture tree (`asr_api.py`, `fluency.py`).
  - Document the DeepInfra direct-call exception and why it exists.
  - Document `ASR_URL`.
  - Update the UI spec for the mode toggle and Fluency panel.
- **`docs/STATUS.md`:** status for each v1 and v2 item (done / partial / not done), with notes. This includes the mp3-through-DeepInfra check and the limits of testing with synthetic audio.
- **README:** mention recording mode and the fluency output. The Space front matter doesn't change.
- **Dependencies:** none change, so `requirements.txt` doesn't need regenerating. This will be confirmed with `uv export` and a diff.
- **Deployment:** the Space's existing `HF_TOKEN` secret must allow calls to Inference Providers. DeepInfra usage is billed to the same HF credits. No new secrets are needed.

**Commit:** `docs: document v2 (recording, fluency, DeepInfra ASR) and add STATUS.md`

---

## Risks and how they're handled

| Risk | Mitigation |
|---|---|
| DeepInfra changes its endpoint or stops serving the model | `ASR_URL` and `ASR_MODEL` are configurable. HTTP 404/5xx map to existing friendly messages. |
| Real hesitant speech loses fillers despite the prompt | The prompt and temperature 0 are the best options available. This is noted in STATUS.md, not hidden. |
| Gradio's microphone output isn't `.wav` | Checked in step 2 before finishing. The recording extension set is adjusted to match. |
| Long recordings exceed payload limits | The existing `MAX_UPLOAD_MB` check applies (25 MB of wav is about 4–13 minutes, depending on sample rate). HTTP 413 maps to the existing message. |
| Timings missing from a response | The transcript is still returned, and Fluency shows "unavailable". |
