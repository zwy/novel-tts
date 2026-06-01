from abc import ABC, abstractmethod
import logging
import shutil
import numpy as np


logger = logging.getLogger(__name__)


class BaseTTSEngine(ABC):
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    @abstractmethod
    def synthesize(self, text: str, voice_profile: str) -> np.ndarray:
        raise NotImplementedError


class FakeTTSEngine(BaseTTSEngine):
    def synthesize(self, text: str, voice_profile: str) -> np.ndarray:
        # 200 ms tone-like placeholder for deterministic tests
        t = np.linspace(0, 0.2, int(self.sample_rate * 0.2), endpoint=False)
        return (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


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

    def __init__(self, model_id: str, sample_rate: int = 24000):
        super().__init__(sample_rate=sample_rate)
        self.model_id = model_id
        self._model = None
        self._model_sample_rate: int = sample_rate

    def _ensure_system_dependencies(self) -> None:
        if shutil.which("sox"):
            return
        raise RuntimeError(
            "SoX is required by qwen-tts but was not found in PATH. "
            "On Windows, run 'choco install sox.portable -y' and restart your shell/service."
        )

    def load(self):
        self._ensure_system_dependencies()
        import torch
        from qwen_tts import Qwen3TTSModel  # pip install qwen-tts

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        self._model = Qwen3TTSModel.from_pretrained(
            self.model_id,
            device_map=device,
            dtype=dtype,
        )

    def synthesize(self, text: str, voice_profile: str) -> np.ndarray:
        if self._model is None:
            self.load()
        speaker, language = self.VOICE_PROFILE_MAP.get(
            voice_profile, self.DEFAULT_SPEAKER
        )
        wavs, sr = self._model.generate_custom_voice(
            text=text,
            language=language,
            speaker=speaker,
        )
        self._model_sample_rate = sr
        logger.info(
            "qwen_tts synthesized voice_profile=%s speaker=%s language=%s sample_rate=%s text_len=%s",
            voice_profile,
            speaker,
            language,
            sr,
            len(text),
        )
        wav = np.array(wavs[0], dtype=np.float32)
        return wav
