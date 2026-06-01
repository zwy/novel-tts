# novel_tts/api.py
import hashlib
from fastapi import FastAPI, Header, HTTPException
from novel_tts.config import Settings

app = FastAPI(title="novel-tts")
settings = Settings()


def check_api_key(x_api_key: str | None):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.post("/v1/tts/jobs")
async def create_job(body: dict, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    if len(body.get("text", "")) > settings.request_body_max_chars:
        raise HTTPException(status_code=400, detail="text too long")
    model_id = body.get("model_id") or settings.default_model_id
    if model_id not in settings.available_models:
        raise HTTPException(status_code=400, detail="unknown model_id")
    text_hash = hashlib.sha256(
        f"{body['text']}|{body.get('voice_profile')}|{model_id}".encode()
    ).hexdigest()
    # repository + worker wiring happens in Task 7
    return {"job_id": "stub-job", "status": "queued", "text_hash": text_hash}


@app.get("/v1/tts/jobs/{job_id}")
async def get_job(job_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    return {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "segments_total": 0,
        "segments_done": 0,
    }


@app.get("/v1/tts/jobs/{job_id}/audio")
async def download_audio(job_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    raise HTTPException(status_code=409, detail="audio not ready")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "model_loaded": True}


@app.get("/v1/models")
async def list_models(x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    return {"default_model_id": settings.default_model_id, "models": settings.available_models}
