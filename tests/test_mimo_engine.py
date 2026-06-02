import base64
import io
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
import soundfile as sf

from novel_tts.mimo_engine import MiMoTTSEngine


# -- Helpers -----------------------------------------------------------------

def _make_wav_bytes(duration_s: float = 0.05, sr: int = 24000) -> bytes:
    """Build a small valid WAV (mono float32 sine) as raw bytes."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    samples = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="FLOAT")
    return buf.getvalue()


def _ok_response(wav_bytes: bytes) -> MagicMock:
    """Build a mock httpx.Response that returns a base64-encoded WAV."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [
            {"message": {"audio": {"data": base64.b64encode(wav_bytes).decode("ascii")}}}
        ]
    }
    return resp


# -- Construction / metadata -------------------------------------------------

def test_mimo_constructor_does_not_require_network():
    # Construction must be cheap; no httpx call until synthesize().
    eng = MiMoTTSEngine(api_key="k", api_base="https://example.com", model="mimo-v2.5-tts")
    assert eng.is_local is False
    assert eng._model_sample_rate == 24000
    assert eng.get_supported_speakers() == [
        "mimo_default", "冰糖", "茉莉", "苏打", "白桦", "Mia", "Chloe", "Milo", "Dean",
    ]
    assert "Chinese" in eng.get_supported_languages()
    assert "English" in eng.get_supported_languages()


def test_mimo_load_is_noop():
    eng = MiMoTTSEngine(api_key="k", api_base="https://example.com", model="mimo-v2.5-tts")
    eng.load()  # must not raise or hit network
    assert eng._model_sample_rate == 24000


# -- synthesize: request shape -----------------------------------------------

def test_synthesize_sends_wav_format_and_passes_voice_through():
    wav_bytes = _make_wav_bytes()
    captured = {}

    def fake_post(url, json, headers, **kwargs):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _ok_response(wav_bytes)

    eng = MiMoTTSEngine(api_key="secret-key", api_base="https://api.xiaomimimo.com/v1",
                        model="mimo-v2.5-tts")
    with patch("novel_tts.mimo_engine.httpx.Client") as ClientCls:
        ClientCls.return_value.__enter__.return_value.post.side_effect = fake_post
        wav = eng.synthesize("你好世界", voice_profile="冰糖")

    assert captured["url"] == "https://api.xiaomimimo.com/v1/chat/completions"
    assert captured["headers"]["api-key"] == "secret-key"
    assert captured["headers"]["Content-Type"] == "application/json"
    payload = captured["json"]
    assert payload["model"] == "mimo-v2.5-tts"
    assert payload["audio"] == {"format": "wav", "voice": "冰糖"}
    # text goes in the assistant message; user is the style hint
    assert payload["messages"][0] == {"role": "user", "content": ""}
    assert payload["messages"][1] == {"role": "assistant", "content": "你好世界"}
    assert isinstance(wav, np.ndarray) and wav.ndim == 1 and wav.size > 0


def test_synthesize_passes_instruct_as_user_message():
    wav_bytes = _make_wav_bytes()
    captured = {}

    def fake_post(url, json, headers, **kwargs):
        captured["json"] = json
        return _ok_response(wav_bytes)

    eng = MiMoTTSEngine(api_key="k", api_base="https://x", model="mimo-v2.5-tts")
    with patch("novel_tts.mimo_engine.httpx.Client") as ClientCls:
        ClientCls.return_value.__enter__.return_value.post.side_effect = fake_post
        eng.synthesize("hi", voice_profile="Chloe", instruct="with a warm tone")

    assert captured["json"]["messages"][0] == {"role": "user", "content": "with a warm tone"}


def test_synthesize_rejects_empty_voice():
    eng = MiMoTTSEngine(api_key="k", api_base="https://x", model="mimo-v2.5-tts")
    with pytest.raises(ValueError, match="voice_profile"):
        eng.synthesize("hello", voice_profile="")


# -- synthesize: response handling -------------------------------------------

def test_synthesize_updates_model_sample_rate_from_response():
    # 16kHz WAV → engine should remember the actual rate so the worker writes
    # the right WAV header.
    wav_bytes = _make_wav_bytes(sr=16000)
    eng = MiMoTTSEngine(api_key="k", api_base="https://x", model="mimo-v2.5-tts",
                        sample_rate=24000)
    with patch("novel_tts.mimo_engine.httpx.Client") as ClientCls:
        ClientCls.return_value.__enter__.return_value.post.return_value = _ok_response(wav_bytes)
        eng.synthesize("hi", voice_profile="Mia")
    assert eng._model_sample_rate == 16000


def test_synthesize_raises_runtime_error_on_http_error():
    import httpx
    eng = MiMoTTSEngine(api_key="k", api_base="https://x", model="mimo-v2.5-tts")
    err = httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock(status_code=401, text="bad key"))
    err.response.status_code = 401
    err.response.text = "bad key"
    with patch("novel_tts.mimo_engine.httpx.Client") as ClientCls:
        ClientCls.return_value.__enter__.return_value.post.side_effect = err
        with pytest.raises(RuntimeError, match="401"):
            eng.synthesize("hi", voice_profile="Mia")


def test_synthesize_raises_on_missing_audio_data():
    eng = MiMoTTSEngine(api_key="k", api_base="https://x", model="mimo-v2.5-tts")
    bad_resp = MagicMock()
    bad_resp.raise_for_status = MagicMock()
    bad_resp.json.return_value = {"choices": [{"message": {}}]}
    with patch("novel_tts.mimo_engine.httpx.Client") as ClientCls:
        ClientCls.return_value.__enter__.return_value.post.return_value = bad_resp
        with pytest.raises(RuntimeError, match="missing audio data"):
            eng.synthesize("hi", voice_profile="Mia")


def test_synthesize_raises_on_invalid_wav_payload():
    eng = MiMoTTSEngine(api_key="k", api_base="https://x", model="mimo-v2.5-tts")
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.json.return_value = {
        "choices": [{"message": {"audio": {"data": base64.b64encode(b"not a wav").decode()}}}]
    }
    with patch("novel_tts.mimo_engine.httpx.Client") as ClientCls:
        ClientCls.return_value.__enter__.return_value.post.return_value = bad
        with pytest.raises(RuntimeError, match="invalid WAV"):
            eng.synthesize("hi", voice_profile="Mia")


# -- _build_instruct (English style) ----------------------------------------

@pytest.mark.parametrize(
    "speed,pitch,volume,expected",
    [
        (None, None, None, None),
        (1.0, 1.0, 1.0, None),
        (1.2, None, None, "speak a bit faster"),
        (0.8, None, None, "speak a bit slower"),
        (None, 1.1, None, "use a slightly higher pitch"),
        (None, 0.9, None, "use a slightly lower pitch"),
        (None, None, 1.3, "use a slightly louder voice"),
        (None, None, 0.7, "use a slightly softer voice"),
        (1.2, 1.1, 1.3, "speak a bit faster, use a slightly higher pitch, use a slightly louder voice"),
        (0.8, 0.9, 0.7, "speak a bit slower, use a slightly lower pitch, use a slightly softer voice"),
    ],
)
def test_build_instruct(speed, pitch, volume, expected):
    result = MiMoTTSEngine._build_instruct(speed, pitch, volume)
    assert result == expected
