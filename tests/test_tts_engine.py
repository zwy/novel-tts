import pytest

import novel_tts.tts_engine as tts_engine
from novel_tts.tts_engine import QwenTTSEngine


def test_qwen_engine_requires_sox(monkeypatch):
    engine = QwenTTSEngine(model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    monkeypatch.setattr(tts_engine.shutil, "which", lambda cmd: None)

    with pytest.raises(RuntimeError, match="SoX"):
        engine._ensure_system_dependencies()


def test_qwen_engine_accepts_when_sox_exists(monkeypatch):
    engine = QwenTTSEngine(model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    monkeypatch.setattr(tts_engine.shutil, "which", lambda cmd: "C:/sox/sox.exe")

    engine._ensure_system_dependencies()


def test_qwen_engine_logs_runtime_voice_mapping(monkeypatch, caplog):
    class FakeModel:
        def generate_custom_voice(self, *, text, language, speaker):
            assert text == "测试文本"
            assert language == "Chinese"
            assert speaker == "Serena"
            return [[0.1, 0.2, 0.3]], 32000

    engine = QwenTTSEngine(model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    engine._model = FakeModel()

    with caplog.at_level("INFO"):
        engine.synthesize("测试文本", voice_profile="female_calm")

    assert "speaker=Serena" in caplog.text
    assert "language=Chinese" in caplog.text
    assert "sample_rate=32000" in caplog.text
    assert "voice_profile=female_calm" in caplog.text