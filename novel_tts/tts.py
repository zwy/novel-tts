"""
tts.py — 文本转语音模块
主要引擎：VoxCPM2（本地，支持中文，高质量）
备用引擎：edge-tts（在线，无需 GPU，轻量）
"""

import os
import math
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────
#  VoxCPM2 引擎（本地推理，需要 GPU 效果更好）
# ─────────────────────────────────────────────

class VoxCPM2Engine:
    """
    使用 OpenBMB/VoxCPM2（2B 参数，支持中文）做 TTS。
    模型首次运行会从 HuggingFace 自动下载（约 4-8 GB）。
    如需离线使用，可提前 huggingface-cli download openbmb/VoxCPM2。
    """

    # 长文本分段阈值（单次推理建议不超过此字数）
    MAX_CHUNK_CHARS = 200

    def __init__(
        self,
        model_id: str = "openbmb/VoxCPM2",
        model_path: Optional[str] = None,
        reference_wav: Optional[str] = None,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10,
    ):
        self.model_id = model_id
        self.model_path = model_path
        self.reference_wav = reference_wav
        self.cfg_value = cfg_value
        self.inference_timesteps = inference_timesteps
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from voxcpm import VoxCPM
        except ImportError:
            raise ImportError("请先安装 voxcpm：pip install voxcpm")

        print("正在加载 VoxCPM2 模型（首次需下载，请耐心等待）...")
        src = self.model_path or self.model_id
        self._model = VoxCPM.from_pretrained(src, load_denoiser=False)
        print("模型加载完成。")

    def _split_text(self, text: str) -> list[str]:
        """
        按句子边界分段，每段不超过 MAX_CHUNK_CHARS 字。
        优先在句号/问号/感叹号处断句。
        """
        # 中文句子结束符
        sentence_endings = r'[。！？!?…\n]+'
        import re
        sentences = re.split(f'({sentence_endings})', text)

        chunks = []
        current = ""
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            punct = sentences[i + 1] if i + 1 < len(sentences) else ""
            part = sentence + punct
            if len(current) + len(part) <= self.MAX_CHUNK_CHARS:
                current += part
            else:
                if current:
                    chunks.append(current.strip())
                current = part
        if current.strip():
            chunks.append(current.strip())
        return chunks

    def synthesize(self, text: str, output_path: str) -> str:
        """
        将文本转为语音，保存到 output_path（.wav）。
        长文本自动分段并拼接。
        返回实际保存路径。
        """
        import soundfile as sf
        import numpy as np

        self._load_model()
        chunks = self._split_text(text)
        total = len(chunks)
        print(f"共 {total} 个分段，开始合成...")

        all_waves = []
        for i, chunk in enumerate(chunks, 1):
            print(f"  [{i}/{total}] {chunk[:30]}...")
            wav = self._model.generate(
                text=chunk,
                prompt_wav_path=self.reference_wav,
                cfg_value=self.cfg_value,
                inference_timesteps=self.inference_timesteps,
                normalize=True,
            )
            all_waves.append(wav)

        merged = np.concatenate(all_waves)
        sr = self._model.tts_model.sample_rate
        sf.write(output_path, merged, sr)
        print(f"音频已保存: {output_path}")
        return output_path


# ─────────────────────────────────────────────
#  edge-tts 备用引擎（在线，无需 GPU，速度快）
# ─────────────────────────────────────────────

class EdgeTTSEngine:
    """
    使用微软 edge-tts 在线服务做 TTS（无需本地模型）。
    输出为 mp3 格式。
    中文推荐声音：zh-CN-XiaoxiaoNeural（女声）/ zh-CN-YunxiNeural（男声）
    繁体中文：zh-TW-HsiaoChenNeural / zh-HK-HiuGaaiNeural
    """

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%"):
        self.voice = voice
        self.rate = rate

    def synthesize(self, text: str, output_path: str) -> str:
        """
        将文本转为语音，保存到 output_path（.mp3）。
        返回实际保存路径。
        """
        try:
            import edge_tts
        except ImportError:
            raise ImportError("请先安装 edge-tts：pip install edge-tts")

        import asyncio

        async def _run():
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
            # 强制使用 .mp3 后缀
            mp3_path = str(Path(output_path).with_suffix('.mp3'))
            await communicate.save(mp3_path)
            return mp3_path

        saved = asyncio.run(_run())
        print(f"音频已保存: {saved}")
        return saved


# ─────────────────────────────────────────────
#  统一入口：根据配置选择引擎
# ─────────────────────────────────────────────

def get_engine(engine: str = "edge", **kwargs):
    """
    engine: "voxcpm2" | "edge"
    kwargs 透传给对应引擎的 __init__
    """
    if engine == "voxcpm2":
        return VoxCPM2Engine(**kwargs)
    elif engine == "edge":
        return EdgeTTSEngine(**kwargs)
    else:
        raise ValueError(f"未知引擎: {engine}。可选值: voxcpm2 / edge")
