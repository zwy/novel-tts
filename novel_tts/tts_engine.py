from abc import ABC, abstractmethod
import logging
import shutil
import sys
import numpy as np
import torch


logger = logging.getLogger(__name__)


class BaseTTSEngine(ABC):
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    @abstractmethod
    def synthesize(self, text: str, voice_profile: str, instruct: str | None = None) -> np.ndarray:
        raise NotImplementedError


class FakeTTSEngine(BaseTTSEngine):
    def synthesize(self, text: str, voice_profile: str, instruct: str | None = None) -> np.ndarray:
        # 200 ms tone-like placeholder for deterministic tests
        t = np.linspace(0, 0.2, int(self.sample_rate * 0.2), endpoint=False)
        return (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    def get_supported_speakers(self) -> list[str]:
        return ["FakeSpeaker"]

    def get_supported_languages(self) -> list[str]:
        return ["Chinese"]


class QwenTTSEngine(BaseTTSEngine):
    # Maps voice_profile names to Qwen3-TTS speaker identifiers.
    # Add custom entries as needed; unknown profiles fall back to "Serena".
    VOICE_PROFILE_MAP: dict[str, tuple[str, str]] = {
        # (speaker, language)
        "female_calm":    ("Serena",    "Chinese"),
        "female_bright":  ("Vivian",    "Chinese"),
        "male_mellow":    ("Uncle_Fu",  "Chinese"),
        "male_beijing":   ("Dylan",     "Chinese"),
        "male_sichuan":   ("Eric",      "Chinese"),
        "male_english":   ("Ryan",      "English"),
        "male_american":  ("Aiden",     "English"),
        "female_japanese":("Ono_Anna",  "Japanese"),
        "female_korean":  ("Sohee",     "Korean"),
    }
    DEFAULT_SPEAKER = ("Serena", "Chinese")

    def __init__(self, model_id: str, sample_rate: int = 24000, use_flash_attention2: bool = False):
        super().__init__(sample_rate=sample_rate)
        self.model_id = model_id
        self.use_flash_attention2 = use_flash_attention2
        self._model = None
        self._model_sample_rate: int = sample_rate

    def _ensure_system_dependencies(self) -> None:
        if shutil.which("sox"):
            return
        raise RuntimeError(
            "SoX is required by qwen-tts but was not found in PATH. "
            "On Windows, run 'choco install sox.portable -y' and restart your shell/service."
        )

    @staticmethod
    def _build_instruct(
        speed: float | None = None,
        pitch: float | None = None,
        volume: float | None = None,
    ) -> str | None:
        """Convert numeric TTS params to a Chinese natural-language instruct for Qwen3-TTS."""
        parts: list[str] = []
        if speed is not None and speed != 1.0:
            if speed < 1.0:
                parts.append("语速稍慢一些")
            else:
                parts.append("语速稍快一些")
        if pitch is not None and pitch != 1.0:
            if pitch < 1.0:
                parts.append("音调稍低一些")
            else:
                parts.append("音调稍高一些")
        if volume is not None and volume != 1.0:
            if volume < 1.0:
                parts.append("音量稍小一些")
            else:
                parts.append("音量稍大一些")
        return "，".join(parts) if parts else None

    def load(self):
        self._ensure_system_dependencies()
        from qwen_tts import Qwen3TTSModel  # pip install qwen-tts

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        attn_impl = None
        if self.use_flash_attention2 and torch.cuda.is_available():
            try:
                import flash_attn  # noqa: F401
                attn_impl = "flash_attention_2"
            except ImportError:
                logger.warning(
                    "flash_attention_2 requested but flash_attn is not installed. "
                    "Falling back to eager attention. Run 'pip install flash-attn --no-build-isolation' to enable."
                )
        logger.info(
            "QwenTTSEngine loading model_id=%s on device=%s dtype=%s cuda_available=%s attn=%s",
            self.model_id, device, dtype, torch.cuda.is_available(), attn_impl or "default",
        )
        kwargs = {}
        if attn_impl:
            kwargs["attn_implementation"] = attn_impl
        self._model = Qwen3TTSModel.from_pretrained(
            self.model_id,
            device_map=device,
            dtype=dtype,
            **kwargs,
        )
        logger.info("QwenTTSEngine model loaded successfully on %s", device)

    def synthesize(self, text: str, voice_profile: str, instruct: str | None = None) -> np.ndarray:
        if self._model is None:
            self.load()
        speaker, language = self.VOICE_PROFILE_MAP.get(
            voice_profile, self.DEFAULT_SPEAKER
        )
        gen_kwargs = dict(
            text=text,
            language=language,
            speaker=speaker,
        )
        if instruct:
            gen_kwargs["instruct"] = instruct
        wavs, sr = self._model.generate_custom_voice(**gen_kwargs)
        self._model_sample_rate = sr
        logger.info(
            "qwen_tts synthesized voice_profile=%s speaker=%s language=%s sample_rate=%s text_len=%s instruct=%s",
            voice_profile,
            speaker,
            language,
            sr,
            len(text),
            instruct,
        )
        wav = np.array(wavs[0], dtype=np.float32)
        return wav

    def get_supported_speakers(self) -> list[str]:
        if self._model is None:
            self.load()
        return self._model.get_supported_speakers()

    def get_supported_languages(self) -> list[str]:
        if self._model is None:
            self.load()
        return self._model.get_supported_languages()
