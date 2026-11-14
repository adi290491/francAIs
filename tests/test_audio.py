import pytest

from tutor.audio.validation import validate_audio
from tutor.core.errors import AudioValidationError

MAX_BYTES = 1024


def _stub(tmp_path, name: str, size: int):
    path = tmp_path / name
    path.write_bytes(b"\x00" * size)
    return path


@pytest.mark.parametrize("name", ["clip.mp3", "CLIP.MP3", "clip.Mp3"])
def test_valid_mp3_accepted_case_insensitive(tmp_path, name):
    path = _stub(tmp_path, name, 100)
    assert validate_audio(str(path), max_bytes=MAX_BYTES) == path


@pytest.mark.parametrize("name", ["clip.wav", "clip.mp3.txt", "clip"])
def test_wrong_extension_rejected(tmp_path, name):
    path = _stub(tmp_path, name, 100)
    with pytest.raises(AudioValidationError, match=r"Only \.mp3"):
        validate_audio(path, max_bytes=MAX_BYTES)


def test_empty_file_rejected(tmp_path):
    path = _stub(tmp_path, "empty.mp3", 0)
    with pytest.raises(AudioValidationError, match="empty"):
        validate_audio(path, max_bytes=MAX_BYTES)


def test_oversize_file_rejected(tmp_path):
    path = _stub(tmp_path, "big.mp3", MAX_BYTES + 1)
    with pytest.raises(AudioValidationError, match="limit"):
        validate_audio(path, max_bytes=MAX_BYTES)


def test_file_at_exact_limit_accepted(tmp_path):
    path = _stub(tmp_path, "edge.mp3", MAX_BYTES)
    assert validate_audio(path, max_bytes=MAX_BYTES) == path


def test_missing_file_rejected(tmp_path):
    with pytest.raises(AudioValidationError, match="could not be found"):
        validate_audio(tmp_path / "gone.mp3", max_bytes=MAX_BYTES)


# --- v2: microphone recordings (.wav) are validated separately from uploads (.mp3) ---


@pytest.mark.parametrize("name", ["audio.wav", "AUDIO.WAV"])
def test_wav_recording_accepted(tmp_path, name):
    path = _stub(tmp_path, name, 100)
    assert validate_audio(path, max_bytes=MAX_BYTES, source="recording") == path


def test_upload_is_default_source(tmp_path):
    path = _stub(tmp_path, "audio.wav", 100)
    with pytest.raises(AudioValidationError, match=r"Only \.mp3"):
        validate_audio(path, max_bytes=MAX_BYTES)


@pytest.mark.parametrize("name", ["clip.mp3", "clip.webm", "clip"])
def test_non_wav_recording_rejected(tmp_path, name):
    path = _stub(tmp_path, name, 100)
    with pytest.raises(AudioValidationError, match=r"recording must be a \.wav"):
        validate_audio(path, max_bytes=MAX_BYTES, source="recording")


def test_empty_recording_rejected(tmp_path):
    path = _stub(tmp_path, "audio.wav", 0)
    with pytest.raises(AudioValidationError, match="recording is empty"):
        validate_audio(path, max_bytes=MAX_BYTES, source="recording")


def test_oversize_recording_rejected(tmp_path):
    path = _stub(tmp_path, "audio.wav", MAX_BYTES + 1)
    with pytest.raises(AudioValidationError, match="recording is .* over the"):
        validate_audio(path, max_bytes=MAX_BYTES, source="recording")


def test_missing_recording_rejected(tmp_path):
    with pytest.raises(AudioValidationError, match="record it again"):
        validate_audio(tmp_path / "gone.wav", max_bytes=MAX_BYTES, source="recording")


def test_unknown_source_is_a_programming_error(tmp_path):
    path = _stub(tmp_path, "clip.mp3", 100)
    with pytest.raises(ValueError):
        validate_audio(path, max_bytes=MAX_BYTES, source="stream")  # type: ignore[arg-type]


# --- silent recordings (muted / wrong microphone) are rejected before any model call ---


def _wav(tmp_path, samples: list[int], name: str = "audio.wav", sampwidth: int = 2):
    import array
    import wave

    path = tmp_path / name
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(sampwidth)
        wav.setframerate(16000)
        if sampwidth == 2:
            wav.writeframes(array.array("h", samples).tobytes())
        else:
            wav.writeframes(bytes(128 for _ in samples))
    return path


@pytest.mark.parametrize("level", [0, 20])  # digital silence, and a faint hiss below -60 dBFS
def test_silent_recording_rejected(tmp_path, level):
    path = _wav(tmp_path, [level, -level] * 8000)
    with pytest.raises(AudioValidationError, match="No sound was picked up"):
        validate_audio(path, max_bytes=10**7, source="recording")


def test_audible_recording_accepted(tmp_path):
    samples = [0] * 8000 + [3000, -3000] * 100 + [0] * 8000  # quiet, then speech-level peaks
    path = _wav(tmp_path, samples)
    assert validate_audio(path, max_bytes=10**7, source="recording") == path


def test_negative_full_scale_peak_is_audible(tmp_path):
    path = _wav(tmp_path, [0] * 100 + [-32768])
    assert validate_audio(path, max_bytes=10**7, source="recording") == path


def test_unreadable_or_non_16_bit_wav_is_left_to_the_provider(tmp_path):
    stub = _stub(tmp_path, "audio.wav", 100)  # not a real WAV
    eight_bit = _wav(tmp_path, [0] * 100, name="eight.wav", sampwidth=1)

    assert validate_audio(stub, max_bytes=MAX_BYTES, source="recording") == stub
    assert validate_audio(eight_bit, max_bytes=MAX_BYTES, source="recording") == eight_bit
