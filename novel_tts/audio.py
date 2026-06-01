# novel_tts/audio.py
from pathlib import Path
import numpy as np
import soundfile as sf


def add_silence(wav: np.ndarray, sample_rate: int, pause_ms: int) -> np.ndarray:
    silence = np.zeros(int(sample_rate * pause_ms / 1000), dtype=wav.dtype)
    return np.concatenate([wav, silence])


def merge_segments(paths: list[Path], out_path: Path, sample_rate: int, pause_ms: int = 160) -> Path:
    signals = []
    for p in paths:
        data, sr = sf.read(p)
        if sr != sample_rate:
            raise ValueError(f"sample rate mismatch: {sr} != {sample_rate}")
        data = data.astype(np.float32)
        signals.append(add_silence(data, sample_rate, pause_ms))
    merged = np.concatenate(signals) if signals else np.array([], dtype=np.float32)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out_path, merged, sample_rate)
    return out_path
