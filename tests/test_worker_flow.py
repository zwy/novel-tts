# tests/test_worker_flow.py
from novel_tts.repository import JobRepository


def test_create_or_get_by_idempotency(session):
    repo = JobRepository(session)
    payload = {
        "request_id": "r1",
        "book_id": "b1",
        "chapter_id": "c1",
        "text": "测试文本",
        "voice_profile": "narrator_default",
        "model_id": "qwen3_tts_0_6b_customvoice",
        "params_json": "{}",
        "text_hash": "h1",
    }
    job1 = repo.create_or_get(payload)
    job2 = repo.create_or_get(payload)
    assert job1.job_id == job2.job_id


from novel_tts.tts_engine import FakeTTSEngine


def test_fake_engine_returns_wav_array():
    eng = FakeTTSEngine(sample_rate=24000)
    wav = eng.synthesize("你好，世界", voice_profile="narrator_default")
    assert wav.ndim == 1
    assert len(wav) > 0


import asyncio
from pathlib import Path
from novel_tts.worker import WorkerService


class WorkerTestCtx:
    def __init__(self, repo, payload, tmp_path):
        self.repo = repo
        self.payload = payload
        engine = FakeTTSEngine(sample_rate=24000)
        tts_engines = {
            "qwen3_tts_0_6b_customvoice": engine,
            "qwen3_tts_1_7b_customvoice": engine,
            "mimo_v2_5_tts": engine,
        }
        self.worker = WorkerService(
            repo=repo,
            tts_engines=tts_engines,
            temp_dir=tmp_path / "temp",
            out_dir=tmp_path / "audio",
            sample_rate=24000,
        )

    def run_once(self):
        job_id = self.worker.queue.get_nowait()
        asyncio.run(self.worker.process_job(job_id))


def test_worker_processes_queued_job_to_succeeded(session, tmp_path):
    from novel_tts.repository import JobRepository
    repo = JobRepository(session)
    payload = {
        "request_id": "r-worker-1",
        "book_id": "book-w",
        "chapter_id": "ch-w1",
        "text": "这是一段测试文本。" * 30,
        "voice_profile": "narrator_default",
        "model_id": "qwen3_tts_0_6b_customvoice",
        "params_json": "{}",
        "text_hash": "h-worker-1",
    }
    ctx = WorkerTestCtx(repo, payload, tmp_path)
    job = ctx.repo.create_or_get(ctx.payload)
    ctx.worker.queue.put_nowait(job.job_id)
    ctx.run_once()
    refreshed = ctx.repo.get(job.job_id)
    assert refreshed.status == "succeeded"
    assert refreshed.audio_path is not None
