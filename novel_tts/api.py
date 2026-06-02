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
from novel_tts.tts_engine import build_engine
from novel_tts.schemas import CreateJobRequest

app = FastAPI(title="novel-tts")
settings = Settings()

# Module-level singletons — replaced via app.state in tests.
_session_factory = create_session_factory(
    settings.db_url, connect_args={"check_same_thread": False}
)
_db_session = _session_factory()
_repo = JobRepository(_db_session)

# Build an engine per registered model. We only skip `enabled=False` entries.
# For enabled entries whose provider can't be constructed right now (e.g. mimo
# without an API key, or Qwen without a GPU), we log a warning and leave that
# model un-initialised — the `/v1/models/{id}/...` endpoints will return 503
# and `POST /v1/tts/jobs` will reject the model with 503 as well, so the
# failure is surfaced cleanly without breaking startup of the rest of the
# service.
_tts_engines: dict[str, object] = {}
for _model_id, _info in settings.model_registry.items():
    if not _info.enabled:
        continue
    try:
        _tts_engines[_model_id] = build_engine(
            _model_id,
            _info,
            fake=settings.use_fake_engine,
            use_flash_attention2=settings.use_flash_attention2,
            mimo_api_key=settings.mimo_api_key,
        )
    except Exception as ex:
        import logging
        logging.getLogger(__name__).warning(
            "Skipping TTS engine for model '%s' (provider=%s): %s",
            _model_id, _info.provider, ex,
        )
_worker = WorkerService(
    repo=_repo,
    tts_engines=_tts_engines,
    temp_dir=Path(settings.temp_dir),
    out_dir=Path(settings.output_dir),
    sample_rate=24000,
)
app.state.repo = _repo
app.state.worker = _worker
app.state.tts_engines = _tts_engines
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
    info = settings.model_registry.get(model_id)
    if info is None or not info.enabled:
        raise HTTPException(status_code=400, detail=f"model_id '{model_id}' is not enabled")
    if model_id not in request.app.state.tts_engines:
        raise HTTPException(
            status_code=503,
            detail=f"model_id '{model_id}' is registered but its engine failed to initialise",
        )
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
    models = []
    for mid in settings.available_models:
        info = settings.model_registry.get(mid)
        if info is None:
            continue
        models.append({
            "id": mid,
            "provider": info.provider,
            "enabled": info.enabled,
            "model_type": info.model_type,
        })
    return {"default_model_id": settings.default_model_id, "models": models}


@app.get("/v1/models/{model_id}/speakers")
async def get_model_speakers(request: Request, model_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    if model_id not in settings.model_registry:
        raise HTTPException(status_code=400, detail="unknown model_id")
    engines = request.app.state.tts_engines
    if model_id not in engines:
        raise HTTPException(status_code=503, detail=f"engine for '{model_id}' not initialised")
    engine = engines[model_id]
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
    engines = request.app.state.tts_engines
    if model_id not in engines:
        raise HTTPException(status_code=503, detail=f"engine for '{model_id}' not initialised")
    engine = engines[model_id]
    try:
        languages = await asyncio.to_thread(engine.get_supported_languages)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"failed to load languages: {ex}")
    return {"model_id": model_id, "languages": languages}
