import pytest

from tutor.core.config import (
    DEFAULT_ASR_MODEL,
    DEFAULT_MAX_UPLOAD_MB,
    DEFAULT_TRANSLATION_MODEL,
    load_settings,
)
from tutor.core.errors import ConfigError


def test_missing_token_says_what_to_set():
    with pytest.raises(ConfigError, match="HF_TOKEN"):
        load_settings({})


def test_blank_token_is_treated_as_missing():
    with pytest.raises(ConfigError, match="HF_TOKEN"):
        load_settings({"HF_TOKEN": "   "})


def test_defaults_applied():
    settings = load_settings({"HF_TOKEN": "hf_test"})
    assert settings.asr_model == DEFAULT_ASR_MODEL
    assert settings.translation_model == DEFAULT_TRANSLATION_MODEL
    assert settings.max_upload_mb == DEFAULT_MAX_UPLOAD_MB
    assert settings.max_upload_bytes == 25 * 1024 * 1024


def test_env_overrides():
    settings = load_settings(
        {
            "HF_TOKEN": "hf_test",
            "ASR_MODEL": "org/asr",
            "TRANSLATION_MODEL": "org/mt",
            "MAX_UPLOAD_MB": "10",
            "INFERENCE_TIMEOUT_S": "30",
        }
    )
    assert settings.asr_model == "org/asr"
    assert settings.translation_model == "org/mt"
    assert settings.max_upload_mb == 10
    assert settings.inference_timeout_s == 30


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_invalid_max_upload_rejected(value):
    with pytest.raises(ConfigError, match="MAX_UPLOAD_MB"):
        load_settings({"HF_TOKEN": "hf_test", "MAX_UPLOAD_MB": value})


def test_token_not_in_repr():
    settings = load_settings({"HF_TOKEN": "hf_secret_value"})
    assert "hf_secret_value" not in repr(settings)
