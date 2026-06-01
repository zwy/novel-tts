from abc import ABC, abstractmethod
import numpy as np


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
    def __init__(self, model_id: str, sample_rate: int = 24000):
        super().__init__(sample_rate=sample_rate)
        self.model_id = model_id
        self._pipeline = None

    def load(self):
        from transformers import pipeline

        self._pipeline = pipeline("text-to-speech", model=self.model_id)

    def synthesize(self, text: str, voice_profile: str) -> np.ndarray:
        if self._pipeline is None:
            self.load()
        output = self._pipeline(text)
        wav = output["audio"]
        if wav.dtype != np.float32:
            wav = wav.astype(np.float32)
        return wav
