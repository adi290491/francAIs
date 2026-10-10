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
