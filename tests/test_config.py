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
