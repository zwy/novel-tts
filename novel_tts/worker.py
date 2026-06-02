# novel_tts/worker.py
import asyncio
import hashlib
import json
from pathlib import Path
import soundfile as sf
from novel_tts.segmentation import split_chapter_text
from novel_tts.audio import merge_segments
from novel_tts.tts_engine import BaseTTSEngine


class WorkerService:
    def __init__(self, repo, tts_engines: dict[str, BaseTTSEngine], temp_dir: Path,
                 out_dir: Path, sample_rate: int = 24000):
        self.repo = repo
        # model_id -> engine. Built once at startup from the model_registry.
        self.tts_engines = tts_engines
        self.temp_dir = temp_dir
        self.out_dir = out_dir
        self.sample_rate = sample_rate
        self.queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, job_id: str):
        await self.queue.put(job_id)

    async def run_forever(self):
        while True:
            job_id = await self.queue.get()
            await self.process_job(job_id)
            self.queue.task_done()

    def _segment_hash(self, text: str, voice_profile: str, model_id: str) -> str:
        """Stable hash for a single segment so identical text/voice/model can be reused."""
        key = f"{model_id}|{voice_profile}|{text}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _resolve_instruct(self, engine: BaseTTSEngine, params: dict) -> str | None:
        """Pick user-provided instruct or build one from speed/pitch/volume via the engine."""
        instruct = params.get("instruct")
        if instruct:
            return instruct
        speed = params.get("speed")
        pitch = params.get("pitch")
        volume = params.get("volume")
        return engine._build_instruct(speed, pitch, volume)

    def _engine_for(self, model_id: str) -> BaseTTSEngine:
        engine = self.tts_engines.get(model_id)
        if engine is None:
            raise RuntimeError(
                f"No TTS engine registered for model_id='{model_id}'. "
                f"Available: {sorted(self.tts_engines.keys())}"
            )
        return engine

    async def process_job(self, job_id: str):
        job = self.repo.get(job_id)
        self.repo.mark_processing(job_id)

        # 1. Final-output cache — if the chapter WAV already exists, skip everything.
        chapter_hash = hashlib.sha256(
            f"{job.book_id}:{job.chapter_id}:{job.text_hash}".encode()
        ).hexdigest()
        out_path = self.out_dir / job.book_id / f"{job.chapter_id}_{chapter_hash[:10]}.wav"
        if out_path.exists():
            self.repo.mark_succeeded(job_id, str(out_path))
            return

        engine = self._engine_for(job.model_id)
        actual_sr = getattr(engine, "_model_sample_rate", self.sample_rate)

        try:
            parts = split_chapter_text(job.input_text)
            self.repo.set_total(job_id, len(parts))
            tmp_paths = []
            cache_dir = self.temp_dir / "segments"
            cache_dir.mkdir(parents=True, exist_ok=True)

            params = json.loads(job.params_json) if job.params_json else {}
            instruct = self._resolve_instruct(engine, params)

            for idx, text in enumerate(parts):
                seg_hash = self._segment_hash(text, job.voice_profile, job.model_id)
                cache_path = cache_dir / f"{seg_hash}.wav"

                if cache_path.exists():
                    # Re-use cached segment.  Sniff sample rate on first hit in case
                    # the engine hasn't been loaded yet.
                    if actual_sr == self.sample_rate:
                        _, actual_sr = await asyncio.to_thread(sf.read, str(cache_path))
                    tmp_paths.append(cache_path)
                    self.repo.set_done(job_id, idx + 1)
                    continue

                # Run synthesis in a background thread so the asyncio event loop
                # stays free for HTTP traffic while long inference (GPU or HTTP) is
                # in progress.
                wav = await asyncio.to_thread(
                    engine.synthesize, text, voice_profile=job.voice_profile, instruct=instruct
                )
                actual_sr = getattr(engine, "_model_sample_rate", self.sample_rate)
                await asyncio.to_thread(sf.write, str(cache_path), wav, actual_sr)
                tmp_paths.append(cache_path)
                self.repo.set_done(job_id, idx + 1)

            await asyncio.to_thread(merge_segments, tmp_paths, out_path, actual_sr)
            self.repo.mark_succeeded(job_id, str(out_path))
        except Exception as ex:
            self.repo.mark_failed(job_id, "INFER_FAIL", str(ex))
