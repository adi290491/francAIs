"""The one place that calls the speech-to-text HTTP endpoint directly.

`InferenceClient.automatic_speech_recognition` drops word timings for every provider that
returns real gaps between words, so transcription posts to DeepInfra's OpenAI-compatible
endpoint (through the Hugging Face router, billed to the same HF credits) instead.
HTTP failures are raised as `HfHubHTTPError`, so `inference_errors` maps them as before.
"""

from pathlib import Path
from typing import Any, Protocol

from huggingface_hub.utils import get_session, hf_raise_for_status

from tutor.core.config import Settings

# Fixed by the v2 spec: force French, literal output, and keep hesitation fillers. The prompt
# primes Whisper's style; without it fillers such as « euh » are silently dropped.
LANGUAGE = "fr"
TEMPERATURE = 0
FILLER_PROMPT = "Euh, alors… je, je voudrais… hum"

_MIME_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav"}


class _Session(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...


def request_transcription(
    audio: Path,
    *,
    settings: Settings,
    session: _Session | None = None,
) -> dict[str, Any]:
    """POST `audio` for transcription and return the decoded `verbose_json` response.

    The response has `text`, `language`, `duration` and `words: [{word, start, end}]`.
    `session` defaults to huggingface_hub's shared HTTP client; tests inject a fake.
    """
    session = session or get_session()
    fields = {
        "model": settings.asr_model,
        "language": LANGUAGE,
        "temperature": str(TEMPERATURE),
        "prompt": FILLER_PROMPT,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "word",
    }
    mime = _MIME_TYPES.get(audio.suffix.lower(), "application/octet-stream")

    with audio.open("rb") as fh:
        response = session.post(
            settings.asr_url,
            # The token only ever travels in this header; it is never logged.
            headers={"Authorization": f"Bearer {settings.hf_token}"},
            data=fields,
            files={"file": (audio.name, fh, mime)},
            timeout=settings.inference_timeout_s,
        )
    hf_raise_for_status(response)
    return response.json()
