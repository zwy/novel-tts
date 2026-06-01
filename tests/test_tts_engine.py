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