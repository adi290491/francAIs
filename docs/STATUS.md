# Status

Last updated: 2026-11-13. Covers every item in the v1 and v2 scope in [CLAUDE.md](../CLAUDE.md).
How v2 was designed is in [PLAN.md](PLAN.md).

**Legend:** ✅ done and verified · 🟡 done, still needs a manual check · ❌ not done

## Summary

| Check | Result |
|---|---|
| `uv run pytest` | 103 passed (no network, no `HF_TOKEN` needed) |
| `uv run ruff check .` / `ruff format` | clean |
| Dependencies | unchanged; `uv export` matches `requirements.txt`, so no regeneration was needed |
| Real API calls (local app, driven with `gradio_client`) | transcribe recording ✅ · translate recording ✅ · transcribe `.mp3` upload ✅ |
| Deployed to the Space | v1 only. The v2 commits are on local `master` and not pushed yet |

## v1 scope

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | File upload (`.mp3` only) | ✅ | Extension check is case-insensitive. Empty, missing and oversize files (`MAX_UPLOAD_MB`, default 25) are rejected before any call. |
| 2 | Transcribe button → French text | ✅ | Since v2 this goes through DeepInfra (see v2 #3). An `.mp3` upload was checked against the real endpoint: the format is accepted and text comes back. The only local mp3 was Gradio's non-speech test clip, so French speech in an `.mp3` has not been checked end to end. |
| 3 | Translate button → English text | ✅ | Reuses `transcriber.transcribe()`, then `Helsinki-NLP/opus-mt-fr-en` through `InferenceClient`. |
| 4 | Output textarea | ✅ | `gr.Textbox(lines=12, interactive=False, buttons=["copy"])` shows the result of the last button pressed. |
| 5 | Gradio Blocks UI | ✅ | Single page with the title "French Tutor" and a one-line description. |
| 6 | Hugging Face deployment | ✅ (v1) | `.github/workflows/deploy-to-hf.yml` force-pushes `master` to the Space's `main`. Earlier fixes covered Python 3.10, the pydantic cap and the ZeroGPU placeholder. The live Space could not be checked from here because `gh` is not installed. |

## v2 scope

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Microphone recording | 🟡 | `gr.Audio(sources=["microphone"], type="filepath")`. The browser recorder lists every available input: built-in, headset, or a phone. **Fixed:** picking a device in the dropdown had no effect (see below). Checked in headless Chrome with fake microphones: the default mic, a picked device, a change of device between recordings, and an Upload↔Record toggle all record from the expected device. A silent mic gives a clear message. **Not yet checked:** a real phone microphone. |
| 2 | Upload/Record toggle | 🟡 | A `gr.Radio(["Upload", "Record"])` shows one input and hides the other. Unit tests cover the visibility updates, the choice of input by mode, and the mode-specific "no audio" warnings. **Not yet checked:** a visual check in the browser, including that a clip survives switching modes. |
| 3 | Transcribe the recording, forced French | ✅ | `language=fr` on DeepInfra `openai/whisper-large-v3`. A real call on hesitant French returned French text. |
| 4 | Translate the recording → English | ✅ | A real call returned "I'd like a coffee, please." Translating also clears the Fluency panel, so old figures never sit next to a new result. Note: opus-mt does not carry the fillers into English. The scope only asks for them in the transcript. |
| 5 | Keep fillers | 🟡 | The filler prompt `Euh, alors… je, je voudrais… hum` and temperature 0 are sent on every call, and the transcript text is returned as is (only extra spaces are collapsed). The step 0 check showed the prompt is needed: without it, an « euh » was dropped. **Limit:** with today's synthetic voice (macOS `say`), « je, je » and « hum » were kept, but the opening « Euh » was dropped and the closing « euh » came back as « hum ». TTS fillers don't sound like real hesitation, so this still needs checking with real hesitant speech. The prompt is the strongest lever Whisper offers. |
| 6 | Word-level timestamps → pauses, words per minute | ✅ | `timestamp_granularities[]=word` gives real gaps between words. `fluency.py` counts gaps of 0.25 s or more as pauses and reports words per minute over the speaking time. Split fragments (`" s"` + `"'il"`) are joined before counting. In the real call, the 0.9 / 1.2 / 0.7 s inserted silences were detected as 3 pauses (1.06 / 1.57 / 0.82 s; the TTS adds its own pauses at punctuation). If a response has no timings, the panel says "Fluency measures unavailable for this recording." |
| 7 | Temperature 0 | ✅ | `temperature=0` is sent on every transcription request (unit tested). |

## Bugs fixed

### Picking a phone (or any non-default microphone) recorded from the default mic

- **Symptom:** after choosing a phone in the recorder's device list, recording starts and the timer runs, but your voice isn't captured.
- **Root cause:** a Gradio 6.30 frontend bug. The recorder's `select.mic-select` dropdown has no change handler, and Record calls `record.startMic()` without a device. That becomes `getUserMedia({audio: true})`, so the browser default mic is always opened.
- **Reproduced:** in headless Chrome with fake devices, choosing "Fake Audio Input 2" opened "Fake Default Audio Input".
- **Fix:** `ui/features/mic_device.js` runs once per page through `demo.load(js=...)`. After the user picks a device, it passes that choice to the browser's microphone request as an exact device ID. If that device has gone, it falls back to the default with a console warning. With the fix, Chrome opened "Fake Audio Input 2". It can be removed once Gradio itself uses the selection.
- **Follow-up: mics that connect later.** Gradio lists devices only once, when the recorder appears, so a phone or headset that became available after that never showed up until a reload. The script now refreshes the dropdown when devices change: new mics are added, and removed ones are greyed out with the selection going back to the default. Checked in Chrome by revealing a hidden fake mic after page load, then picking it and recording from it.
- **Follow-up: first recording silent on a phone mic.** The first recording after picking the phone came out silent; the second worked. Gradio starts recording the moment the device opens, but a Continuity iPhone mic (or Bluetooth earphones switching to their mic) sends digital silence for a while, and sometimes not at all on the first open. The script now does four things:
  - It waits until the mic actually sends audio before recording starts.
  - If nothing arrives within 3 s, it reopens the device once.
  - It starts connecting a device as soon as you pick it.
  - The Record button shows "connecting mic…" and ignores clicks during the wait.

  Checked in Chrome with simulated mics for three cases: a phone that is slow to start (2.5 s), a phone that is silent on its first open, and a slow default mic. The first recording now has sound from its first few milliseconds; before, it lost 2.5 s or everything.
- **Phone mic on a Mac:** a browser can only list mics that macOS offers. An iPhone appears as "iPhone Microphone" through Continuity only while it is nearby on the same Apple ID, with Wi-Fi and Bluetooth on and Continuity Camera enabled on the phone. It has to show under System Settings → Sound → Input before any browser can use it.
- **Safety net:** a recording with no audible sound (peak below -60 dBFS) is now rejected before any model call, with a message to check the selected microphone. This stops Whisper inventing text from silence.

## Deliberate deviation from CLAUDE.md

Transcription no longer uses `InferenceClient`. It sends a direct `POST` to DeepInfra's OpenAI-compatible endpoint through the HF router (`tutor/core/asr_api.py`, URL configurable with `ASR_URL`). This was approved in the plan, because no `InferenceClient` route returns usable word timings. HTTP errors still go through `inference_errors`, so the friendly messages for 401/402/404/413/429/5xx and timeouts are unchanged.

## Manual steps left for you

1. **Browser check** (`uv run python app.py`):
   - record a clip and check the device picker
   - switch between Upload and Record and check that both clips are kept
   - press Transcribe and check that Output and Fluency both fill
   - press Translate and check for English
2. **Real hesitant speech:** record yourself with real « euh » / « hum » and check they appear in the transcript (v2 #5).
3. **Push** `master` to deploy v2. No new secrets are needed. The Space's existing `HF_TOKEN` must be allowed to call Inference Providers, because DeepInfra usage is billed to the same HF credits.
4. **On the Space:** record from a phone browser to confirm mobile microphones work over HTTPS.
5. **Phone as microphone:** pick your phone in the device list (for example an iPhone through Continuity, or a Bluetooth headset), record, and play the clip back. It should be your voice from the phone.
