"""Cloud TTS provider backed by Xiaomi MiMo TTS (https://platform.xiaomimimo.com).

MiMo exposes an OpenAI-Chat-Completions compatible endpoint at
``https://api.xiaomimimo.com/v1/chat/completions``. We only use the *preset-voice*
model ``mimo-v2.5-tts`` here; the audio bytes come back base64-encoded inside
``choices[0].message.audio.data``.

This engine is a *cloud* engine: it does not load any model into local memory.
The constructor is cheap and ``load()`` is a no-op, so the engine is safe to
construct at app startup even when the API key is missing — the worker will only
fail at the first ``synthesize`` call.
"""
import base64
import io
import logging

import httpx
import numpy as np
import soundfile as sf

from novel_tts.tts_engine import BaseTTSEngine


logger = logging.getLogger(__name__)


class MiMoTTSEngine(BaseTTSEngine):
    is_local = False

    # 8 preset voices (4 Chinese, 4 English) plus the platform default.
    # Voice IDs are passed straight through to the MiMo API as `audio.voice`.
    SUPPORTED_VOICES: list[str] = [
        "mimo_default",
        "冰糖", "茉莉", "苏打", "白桦",
        "Mia", "Chloe", "Milo", "Dean",
    ]

    def __init__(self, api_key: str, api_base: str, model: str, sample_rate: int = 24000):
        super().__init__(sample_rate=sample_rate)
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        # Worker duck-types on this attribute; default to the configured sample rate
        # and update it once we decode the first response.
        self._model_sample_rate: int = sample_rate

    def load(self) -> None:
        """No-op for cloud engines; the engine is ready as soon as it is constructed."""
        return None

    def synthesize(self, text: str, voice_profile: str, instruct: str | None = None) -> np.ndarray:
        if not voice_profile:
            raise ValueError("MiMoTTSEngine.synthesize requires a non-empty voice_profile "
                             "(used as the MiMo voice id, e.g. 'Chloe' or '冰糖').")
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": instruct or ""},
                {"role": "assistant", "content": text},
            ],
            "audio": {
                "format": "wav",
                "voice": voice_profile,
            },
        }
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

        logger.info(
            "mimo_tts request model=%s voice=%s text_len=%d instruct=%s",
            self.model, voice_profile, len(text), bool(instruct),
        )
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPStatusError as ex:
            # Surface the upstream error body in the worker log for easier debugging.
            body = ""
            try:
                body = ex.response.text[:512]
            except Exception:  # pragma: no cover
                pass
            raise RuntimeError(
                f"MiMo TTS HTTP {ex.response.status_code} for voice={voice_profile}: {body}"
            ) from ex
        except httpx.HTTPError as ex:
            raise RuntimeError(f"MiMo TTS request failed: {ex}") from ex

        body_json = resp.json()
        try:
            audio_b64 = body_json["choices"][0]["message"]["audio"]["data"]
        except (KeyError, IndexError, TypeError) as ex:
            raise RuntimeError(
                f"MiMo TTS response missing audio data: {body_json!r}"
            ) from ex

        audio_bytes = base64.b64decode(audio_b64)
        try:
            wav, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        except Exception as ex:
            raise RuntimeError(f"MiMo TTS returned invalid WAV data: {ex}") from ex

        self._model_sample_rate = int(sr)
        logger.info(
            "mimo_tts synthesized voice=%s sample_rate=%d samples=%d",
            voice_profile, sr, len(wav),
        )
        # `sf.read` returns mono as 1-D and stereo as 2-D; the worker expects 1-D
        # (the segment-merge logic assumes a single channel).
        arr = np.asarray(wav, dtype=np.float32)
        if arr.ndim > 1:
            arr = arr.mean(axis=1).astype(np.float32)
        return arr

    def get_supported_speakers(self) -> list[str]:
        return list(self.SUPPORTED_VOICES)

    def get_supported_languages(self) -> list[str]:
        return ["Chinese", "English"]

    @staticmethod
    def _build_instruct(
        speed: float | None = None,
        pitch: float | None = None,
        volume: float | None = None,
    ) -> str | None:
        """Convert numeric TTS params to short English natural-language phrases for MiMo.

        MiMo accepts free-form style hints in the ``user`` message, so we just
        build a short comma-separated sentence describing the deviations from
        defaults. Defaults (1.0) are omitted to keep the hint clean.
        """
        parts: list[str] = []
        if speed is not None and speed != 1.0:
            parts.append("speak a bit faster" if speed > 1.0 else "speak a bit slower")
        if pitch is not None and pitch != 1.0:
            parts.append("use a slightly higher pitch" if pitch > 1.0 else "use a slightly lower pitch")
        if volume is not None and volume != 1.0:
            parts.append("use a slightly louder voice" if volume > 1.0 else "use a slightly softer voice")
        return ", ".join(parts) if parts else None
