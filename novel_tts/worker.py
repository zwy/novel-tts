# novel_tts/worker.py
import asyncio
import hashlib
from pathlib import Path
import soundfile as sf
from novel_tts.segmentation import split_chapter_text
from novel_tts.audio import merge_segments


class WorkerService:
    def __init__(self, repo, tts_engine, temp_dir: Path, out_dir: Path, sample_rate: int = 24000):
        self.repo = repo
        self.tts_engine = tts_engine
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

    async def process_job(self, job_id: str):
        job = self.repo.get(job_id)
        self.repo.mark_processing(job_id)
        try:
            parts = split_chapter_text(job.input_text)
            self.repo.set_total(job_id, len(parts))
            tmp_paths = []
            for idx, text in enumerate(parts):
                wav = self.tts_engine.synthesize(text, voice_profile=job.voice_profile)
                temp = self.temp_dir / f"{job_id}_{idx:04d}.wav"
                temp.parent.mkdir(parents=True, exist_ok=True)
                sf.write(temp, wav, self.sample_rate)
                tmp_paths.append(temp)
                self.repo.set_done(job_id, idx + 1)

            chapter_hash = hashlib.sha256(
                f"{job.book_id}:{job.chapter_id}:{job.text_hash}".encode()
            ).hexdigest()
            out_path = self.out_dir / job.book_id / f"{job.chapter_id}_{chapter_hash[:10]}.wav"
            merge_segments(tmp_paths, out_path, self.sample_rate)
            self.repo.mark_succeeded(job_id, str(out_path))
        except Exception as ex:
            self.repo.mark_failed(job_id, "INFER_FAIL", str(ex))
