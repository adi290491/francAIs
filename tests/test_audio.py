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
