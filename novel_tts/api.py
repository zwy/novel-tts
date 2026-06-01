# novel_tts/api.py
import asyncio
import hashlib
import json
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from novel_tts.config import Settings
from novel_tts.db import create_session_factory
from novel_tts.repository import JobRepository
from novel_tts.worker import WorkerService
from novel_tts.tts_engine import FakeTTSEngine, QwenTTSEngine
from novel_tts.schemas import CreateJobRequest

app = FastAPI(title="novel-tts")
settings = Settings()

# Module-level singletons — replaced via app.state in tests
_session_factory = create_session_factory(
    settings.db_url, connect_args={"check_same_thread": False}
)
_db_session = _session_factory()
_repo = JobRepository(_db_session)
if settings.use_fake_engine:
    _tts_engine = FakeTTSEngine(sample_rate=24000)
else:
    _hf_repo = settings.model_registry[settings.default_model_id].hf_repo
    _tts_engine = QwenTTSEngine(
        model_id=_hf_repo,
        sample_rate=24000,
        use_flash_attention2=settings.use_flash_attention2,
    )
_worker = WorkerService(
    repo=_repo,
    tts_engine=_tts_engine,
    temp_dir=Path(settings.temp_dir),
    out_dir=Path(settings.output_dir),
    sample_rate=24000,
)
app.state.repo = _repo
app.state.worker = _worker
app.state.tts_engine = _tts_engine
app.state.worker_task = None


@app.on_event("startup")
async def start_worker_loop() -> None:
    # Start one background consumer per application process.
    app.state.worker_task = asyncio.create_task(app.state.worker.run_forever())


@app.on_event("shutdown")
async def stop_worker_loop() -> None:
    task = app.state.worker_task
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    app.state.worker_task = None


def check_api_key(x_api_key: str | None):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.post("/v1/tts/jobs")
async def create_job(request: Request, body: CreateJobRequest, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    repo = request.app.state.repo
    worker = request.app.state.worker
    if len(body.text) > settings.request_body_max_chars:
        raise HTTPException(status_code=400, detail="text too long")
    model_id = body.model_id or settings.default_model_id
    if model_id not in settings.available_models:
        raise HTTPException(status_code=400, detail="unknown model_id")
    text_hash = hashlib.sha256(
        f"{body.text}|{body.voice_profile}|{model_id}".encode()
    ).hexdigest()
    payload = {
        "request_id": body.request_id,
        "book_id": body.book_id,
        "chapter_id": body.chapter_id,
        "text": body.text,
        "voice_profile": body.voice_profile,
        "model_id": model_id,
        "params_json": json.dumps(body.model_dump(mode="json"), ensure_ascii=False),
        "text_hash": text_hash,
    }
    job = repo.create_or_get(payload)
    await worker.enqueue(job.job_id)
    return {"job_id": job.job_id, "status": job.status}


@app.get("/v1/tts/jobs/{job_id}")
async def get_job(request: Request, job_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    repo = request.app.state.repo
    try:
        job = repo.get(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="job not found")
    progress = 0
    if job.segments_total > 0:
        progress = int(job.segments_done / job.segments_total * 100)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": progress,
        "segments_total": job.segments_total,
        "segments_done": job.segments_done,
        "audio_url": f"/v1/tts/jobs/{job_id}/audio" if job.status == "succeeded" else None,
        "error_code": job.error_code,
        "error_message": job.error_message,
    }


@app.get("/v1/tts/jobs/{job_id}/audio")
async def download_audio(request: Request, job_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    repo = request.app.state.repo
    try:
        job = repo.get(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != "succeeded" or not job.audio_path:
        raise HTTPException(status_code=409, detail="audio not ready")
    audio_path = Path(job.audio_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="audio file missing")
    return FileResponse(str(audio_path), media_type="audio/wav")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "model_loaded": True}


@app.get("/v1/models")
async def list_models(x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    return {"default_model_id": settings.default_model_id, "models": settings.available_models}


@app.get("/v1/models/{model_id}/speakers")
async def get_model_speakers(request: Request, model_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    if model_id not in settings.model_registry:
        raise HTTPException(status_code=400, detail="unknown model_id")
    engine = request.app.state.tts_engine
    try:
        speakers = await asyncio.to_thread(engine.get_supported_speakers)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"failed to load speakers: {ex}")
    return {"model_id": model_id, "speakers": speakers}


@app.get("/v1/models/{model_id}/languages")
async def get_model_languages(request: Request, model_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    if model_id not in settings.model_registry:
        raise HTTPException(status_code=400, detail="unknown model_id")
    engine = request.app.state.tts_engine
    try:
        languages = await asyncio.to_thread(engine.get_supported_languages)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"failed to load languages: {ex}")
    return {"model_id": model_id, "languages": languages}
