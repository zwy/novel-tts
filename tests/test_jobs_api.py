from novel_tts.config import Settings


def test_default_model_in_available_models():
    s = Settings()
    assert s.default_model_id in s.available_models
    assert "qwen3_tts_0_6b_customvoice" in s.available_models
