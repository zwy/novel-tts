import pytest
from novel_tts.config import Settings, ModelInfo


def test_default_model_in_available_models():
    s = Settings()
    assert s.default_model_id in s.available_models
    assert "qwen3_tts_0_6b_customvoice" in s.available_models


def test_validator_rejects_default_model_not_in_registry():
    with pytest.raises(Exception):
        Settings(
            default_model_id="nonexistent",
            available_models=["nonexistent"],
            model_registry={},
        )


def test_validator_rejects_available_model_not_in_registry():
    with pytest.raises(Exception):
        Settings(
            default_model_id="qwen3_tts_0_6b_customvoice",
            available_models=["qwen3_tts_0_6b_customvoice", "ghost_model"],
            model_registry={
                "qwen3_tts_0_6b_customvoice": ModelInfo(
                    hf_repo="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", enabled=True
                )
            },
        )


def test_mimo_model_present_in_default_registry():
    s = Settings()
    info = s.model_registry["mimo_v2_5_tts"]
    assert info.provider == "mimo"
    # enabled=True by default: a configured MIMO_API_KEY is enough to use it.
    # The api.py layer gracefully skips construction if the key is missing.
    assert info.enabled is True
    assert info.provider_config["api_base"] == "https://api.xiaomimimo.com/v1"
    assert info.provider_config["model"] == "mimo-v2.5-tts"


def test_validator_rejects_unknown_provider():
    with pytest.raises(Exception):
        Settings(
            default_model_id="mimo_v2_5_tts",
            available_models=["mimo_v2_5_tts"],
            model_registry={
                "mimo_v2_5_tts": ModelInfo(
                    hf_repo="mimo-v2.5-tts", provider="bogus_provider"
                ),
            },
        )


def test_mimo_api_key_setting_default_empty():
    s = Settings()
    assert s.mimo_api_key == ""
