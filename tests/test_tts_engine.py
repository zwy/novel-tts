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
        def generate_custom_voice(self, *, text, language, speaker, instruct=None):
            assert text == "测试文本"
            assert language == "Chinese"
            assert speaker == "Serena"
            assert instruct is None
            return [[0.1, 0.2, 0.3]], 32000

    engine = QwenTTSEngine(model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    engine._model = FakeModel()

    with caplog.at_level("INFO"):
        engine.synthesize("测试文本", voice_profile="female_calm")

    assert "speaker=Serena" in caplog.text
    assert "language=Chinese" in caplog.text
    assert "sample_rate=32000" in caplog.text
    assert "voice_profile=female_calm" in caplog.text


def test_qwen_engine_passes_instruct(monkeypatch, caplog):
    class FakeModel:
        def generate_custom_voice(self, *, text, language, speaker, instruct=None):
            assert instruct == "用温柔的语气说"
            return [[0.1, 0.2, 0.3]], 24000

    engine = QwenTTSEngine(model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    engine._model = FakeModel()

    with caplog.at_level("INFO"):
        engine.synthesize("测试文本", voice_profile="female_calm", instruct="用温柔的语气说")

    assert "instruct=用温柔的语气说" in caplog.text


@pytest.mark.parametrize(
    "speed,pitch,volume,expected",
    [
        (None, None, None, None),
        (1.0, 1.0, 1.0, None),
        (1.2, None, None, "语速稍快一些"),
        (0.8, None, None, "语速稍慢一些"),
        (None, 1.1, None, "音调稍高一些"),
        (None, 0.9, None, "音调稍低一些"),
        (None, None, 1.3, "音量稍大一些"),
        (None, None, 0.7, "音量稍小一些"),
        (1.2, 1.1, 1.3, "语速稍快一些，音调稍高一些，音量稍大一些"),
        (0.8, 0.9, 0.7, "语速稍慢一些，音调稍低一些，音量稍小一些"),
    ],
)
def test_build_instruct(speed, pitch, volume, expected):
    result = QwenTTSEngine._build_instruct(speed, pitch, volume)
    assert result == expected


def test_qwen_engine_loads_with_flash_attention2(monkeypatch):
    captured = {}

    class FakeQwenModel:
        @classmethod
        def from_pretrained(cls, model_id, device_map, dtype, **kwargs):
            captured["model_id"] = model_id
            captured["device_map"] = device_map
            captured["dtype"] = dtype
            captured["kwargs"] = kwargs
            return cls()

    monkeypatch.setattr(tts_engine.shutil, "which", lambda cmd: "/usr/bin/sox")
    monkeypatch.setattr(tts_engine.torch.cuda, "is_available", lambda: True)

    # Mock qwen_tts module so the import in load() succeeds
    fake_qwen_tts = type("Module", (), {"Qwen3TTSModel": FakeQwenModel})()
    monkeypatch.setitem(tts_engine.sys.modules, "qwen_tts", fake_qwen_tts)

    engine = QwenTTSEngine(
        model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        use_flash_attention2=True,
    )
    # Simulate flash_attn installed
    fake_flash_attn = type("Module", (), {})()
    monkeypatch.setitem(tts_engine.sys.modules, "flash_attn", fake_flash_attn)
    engine.load()

    assert captured["kwargs"].get("attn_implementation") == "flash_attention_2"


def test_qwen_engine_loads_fallback_without_flash_attn(monkeypatch):
    captured = {}

    class FakeQwenModel:
        @classmethod
        def from_pretrained(cls, model_id, device_map, dtype, **kwargs):
            captured["kwargs"] = kwargs
            return cls()

    monkeypatch.setattr(tts_engine.shutil, "which", lambda cmd: "/usr/bin/sox")
    monkeypatch.setattr(tts_engine.torch.cuda, "is_available", lambda: True)

    # Mock qwen_tts module so the import in load() succeeds
    fake_qwen_tts = type("Module", (), {"Qwen3TTSModel": FakeQwenModel})()
    monkeypatch.setitem(tts_engine.sys.modules, "qwen_tts", fake_qwen_tts)

    engine = QwenTTSEngine(
        model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        use_flash_attention2=True,
    )
    # flash_attn not installed → should fall back gracefully
    if "flash_attn" in tts_engine.sys.modules:
        del tts_engine.sys.modules["flash_attn"]
    engine.load()

    assert "attn_implementation" not in captured["kwargs"]


def test_qwen_engine_get_supported_speakers(monkeypatch):
    class FakeModel:
        def get_supported_speakers(self):
            return ["Serena", "Ryan"]

    engine = QwenTTSEngine(model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    engine._model = FakeModel()
    assert engine.get_supported_speakers() == ["Serena", "Ryan"]


def test_qwen_engine_get_supported_languages(monkeypatch):
    class FakeModel:
        def get_supported_languages(self):
            return ["Chinese", "English"]

    engine = QwenTTSEngine(model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    engine._model = FakeModel()
    assert engine.get_supported_languages() == ["Chinese", "English"]
