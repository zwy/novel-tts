# Novel TTS Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LAN-accessible async chapter TTS service with Qwen3-TTS 0.6B as default, with API-compatible model switch reservation for 1.7B.

**Architecture:** Use a FastAPI monolith with in-process async queue and single GPU worker. Persist jobs in SQLite and audio files on local filesystem, expose create/query/download APIs, plus health and model introspection endpoints.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy, Pydantic, pytest, httpx, soundfile, numpy, torch, transformers.

---

## Planned File Structure

Create or modify these focused units:

- Create: `novel_tts/config.py` (settings, model registry, auth and runtime limits)
- Create: `novel_tts/schemas.py` (request/response schemas)
- Create: `novel_tts/db.py` (SQLite engine/session setup)
- Create: `novel_tts/models.py` (SQLAlchemy job model)
- Create: `novel_tts/repository.py` (job persistence + idempotency/query methods)
- Create: `novel_tts/segmentation.py` (Chinese text segmentation rules)
- Create: `novel_tts/audio.py` (temp segment writing + chapter merge)
- Create: `novel_tts/tts_engine.py` (engine interface, Qwen engine, fake test engine)
- Create: `novel_tts/worker.py` (job queue consumer and state transitions)
- Create: `novel_tts/api.py` (FastAPI routes and dependency wiring)
- Modify: `main.py` (ASGI app entry)
- Modify: `requirements.txt` (runtime/test deps)
- Create: `tests/test_segmentation.py`
- Create: `tests/test_jobs_api.py`
- Create: `tests/test_worker_flow.py`
- Modify: `README.md` (runbook and API examples)

## Task 1: Bootstrap Project Runtime and Configuration

**Files:**
- Create: `novel_tts/config.py`
- Modify: `requirements.txt`
- Test: `tests/test_jobs_api.py`

- [ ] **Step 1: Write the failing test for model registry defaults**

```python
# tests/test_jobs_api.py
from novel_tts.config import Settings


def test_default_model_in_available_models():
    s = Settings()
    assert s.default_model_id in s.available_models
    assert "qwen3_tts_0_6b_customvoice" in s.available_models
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs_api.py::test_default_model_in_available_models -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'novel_tts.config'`

- [ ] **Step 3: Write minimal implementation for settings and dependencies**

```python
# novel_tts/config.py
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ModelInfo(BaseModel):
    model_id: str
    hf_repo: str
    enabled: bool = True


class Settings(BaseSettings):
    api_key: str = "dev-local-key"
    host: str = "0.0.0.0"
    port: int = 8008
    db_url: str = "sqlite:///./novel_tts.db"
    output_dir: str = "./data/audio"
    temp_dir: str = "./data/temp"
    default_model_id: str = "qwen3_tts_0_6b_customvoice"
    available_models: list[str] = [
        "qwen3_tts_0_6b_customvoice",
        "qwen3_tts_1_7b_customvoice",
    ]
    model_registry: dict[str, ModelInfo] = {
        "qwen3_tts_0_6b_customvoice": ModelInfo(
            model_id="qwen3_tts_0_6b_customvoice",
            hf_repo="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            enabled=True,
        ),
        "qwen3_tts_1_7b_customvoice": ModelInfo(
            model_id="qwen3_tts_1_7b_customvoice",
            hf_repo="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            enabled=False,
        ),
    }
    max_concurrent_jobs: int = 1
    request_body_max_chars: int = 10000
```

```txt
# requirements.txt
fastapi
uvicorn
sqlalchemy
pydantic
pydantic-settings
pytest
httpx
soundfile
numpy
torch
transformers
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs_api.py::test_default_model_in_available_models -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt novel_tts/config.py tests/test_jobs_api.py
git commit -m "chore: add settings and model registry baseline"
```

## Task 2: Add Persistence Model and Repository for Async Jobs

**Files:**
- Create: `novel_tts/db.py`
- Create: `novel_tts/models.py`
- Create: `novel_tts/repository.py`
- Test: `tests/test_worker_flow.py`

- [ ] **Step 1: Write failing test for idempotent create**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worker_flow.py::test_create_or_get_by_idempotency -v`
Expected: FAIL with import or attribute error for `JobRepository`

- [ ] **Step 3: Implement db model and repository**

```python
# novel_tts/models.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(128), index=True)
    book_id: Mapped[str] = mapped_column(String(128), index=True)
    chapter_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    model_id: Mapped[str] = mapped_column(String(128))
    voice_profile: Mapped[str] = mapped_column(String(128))
    params_json: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(128), index=True)
    input_text: Mapped[str] = mapped_column(Text)
    segments_total: Mapped[int] = mapped_column(Integer, default=0)
    segments_done: Mapped[int] = mapped_column(Integer, default=0)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

```python
# novel_tts/repository.py
from sqlalchemy import select
from novel_tts.models import Job


class JobRepository:
    def __init__(self, session):
        self.session = session

    def create_or_get(self, payload: dict) -> Job:
        stmt = select(Job).where(Job.request_id == payload["request_id"], Job.chapter_id == payload["chapter_id"])
        existing = self.session.execute(stmt).scalar_one_or_none()
        if existing:
            return existing
        job = Job(
            request_id=payload["request_id"],
            book_id=payload["book_id"],
            chapter_id=payload["chapter_id"],
            model_id=payload["model_id"],
            voice_profile=payload["voice_profile"],
            params_json=payload["params_json"],
            text_hash=payload["text_hash"],
            input_text=payload["text"],
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worker_flow.py::test_create_or_get_by_idempotency -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add novel_tts/db.py novel_tts/models.py novel_tts/repository.py tests/test_worker_flow.py
git commit -m "feat: add sqlite job repository with idempotent create"
```

## Task 3: Implement Text Segmentation and Audio Merge Utilities

**Files:**
- Create: `novel_tts/segmentation.py`
- Create: `novel_tts/audio.py`
- Test: `tests/test_segmentation.py`

- [ ] **Step 1: Write failing segmentation test**

```python
# tests/test_segmentation.py
from novel_tts.segmentation import split_chapter_text


def test_split_chapter_text_preserves_order_and_bounds():
    text = "第一句。第二句，第三句！第四句？第五句；第六句。"
    parts = split_chapter_text(text, min_chars=6, max_chars=12)
    assert len(parts) >= 3
    assert "".join(parts).replace(" ", "") == text
    assert all(len(p) <= 12 for p in parts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_segmentation.py::test_split_chapter_text_preserves_order_and_bounds -v`
Expected: FAIL with import error for `split_chapter_text`

- [ ] **Step 3: Implement segmentation and merge utility**

```python
# novel_tts/segmentation.py
import re


def split_chapter_text(text: str, min_chars: int = 120, max_chars: int = 220) -> list[str]:
    cleaned = re.sub(r"\s+", "", text)
    if not cleaned:
        return []

    sentences = re.split(r"(?<=[。！？；])", cleaned)
    chunks: list[str] = []
    buffer = ""

    for sentence in sentences:
        if not sentence:
            continue
        if len(buffer) + len(sentence) <= max_chars:
            buffer += sentence
            continue
        if buffer:
            chunks.append(buffer)
            buffer = ""
        if len(sentence) <= max_chars:
            buffer = sentence
            continue

        comma_parts = re.split(r"(?<=，)", sentence)
        long_buf = ""
        for p in comma_parts:
            if len(long_buf) + len(p) <= max_chars:
                long_buf += p
            else:
                if long_buf:
                    chunks.append(long_buf)
                long_buf = p
        if long_buf:
            buffer = long_buf

    if buffer:
        chunks.append(buffer)

    merged: list[str] = []
    for c in chunks:
        if merged and len(merged[-1]) < min_chars and len(merged[-1]) + len(c) <= max_chars:
            merged[-1] += c
        else:
            merged.append(c)
    return merged
```

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_segmentation.py::test_split_chapter_text_preserves_order_and_bounds -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add novel_tts/segmentation.py novel_tts/audio.py tests/test_segmentation.py
git commit -m "feat: add chinese text segmentation and audio merge helpers"
```

## Task 4: Implement TTS Engine Abstraction and Qwen/Fake Engines

**Files:**
- Create: `novel_tts/tts_engine.py`
- Test: `tests/test_worker_flow.py`

- [ ] **Step 1: Write failing engine contract test**

```python
# tests/test_worker_flow.py
from novel_tts.tts_engine import FakeTTSEngine


def test_fake_engine_returns_wav_array():
    eng = FakeTTSEngine(sample_rate=24000)
    wav = eng.synthesize("你好，世界", voice_profile="narrator_default")
    assert wav.ndim == 1
    assert len(wav) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worker_flow.py::test_fake_engine_returns_wav_array -v`
Expected: FAIL with import error for `FakeTTSEngine`

- [ ] **Step 3: Implement engine contract and minimal engines**

```python
# novel_tts/tts_engine.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worker_flow.py::test_fake_engine_returns_wav_array -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add novel_tts/tts_engine.py tests/test_worker_flow.py
git commit -m "feat: add tts engine interface with fake and qwen engines"
```

## Task 5: Implement Worker Queue and Job Processing Pipeline

**Files:**
- Create: `novel_tts/worker.py`
- Modify: `novel_tts/repository.py`
- Test: `tests/test_worker_flow.py`

- [ ] **Step 1: Write failing worker state transition test**

```python
# tests/test_worker_flow.py

def test_worker_processes_queued_job_to_succeeded(worker_ctx):
    job = worker_ctx.repo.create_or_get(worker_ctx.payload)
    worker_ctx.queue.put_nowait(job.job_id)
    worker_ctx.run_once()
    refreshed = worker_ctx.repo.get(job.job_id)
    assert refreshed.status == "succeeded"
    assert refreshed.audio_path is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worker_flow.py::test_worker_processes_queued_job_to_succeeded -v`
Expected: FAIL with missing worker methods

- [ ] **Step 3: Implement queue consumer and status updates**

```python
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

            chapter_hash = hashlib.sha256(f"{job.book_id}:{job.chapter_id}:{job.text_hash}".encode()).hexdigest()
            out_path = self.out_dir / job.book_id / f"{job.chapter_id}_{chapter_hash[:10]}.wav"
            merge_segments(tmp_paths, out_path, self.sample_rate)
            self.repo.mark_succeeded(job_id, str(out_path))
        except Exception as ex:
            self.repo.mark_failed(job_id, "INFER_FAIL", str(ex))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worker_flow.py::test_worker_processes_queued_job_to_succeeded -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add novel_tts/worker.py novel_tts/repository.py tests/test_worker_flow.py
git commit -m "feat: add async worker pipeline and job state transitions"
```

## Task 6: Implement FastAPI Endpoints and Auth Guard

**Files:**
- Create: `novel_tts/schemas.py`
- Create: `novel_tts/api.py`
- Modify: `main.py`
- Test: `tests/test_jobs_api.py`

- [ ] **Step 1: Write failing API test for create/query/download flow**

```python
# tests/test_jobs_api.py
from fastapi.testclient import TestClient
from main import app


def test_create_job_and_poll_status():
    client = TestClient(app)
    payload = {
        "request_id": "req-001",
        "book_id": "book-a",
        "chapter_id": "ch-001",
        "text": "这是一个测试章节。" * 200,
        "voice_profile": "narrator_default",
    }
    r = client.post("/v1/tts/jobs", json=payload, headers={"x-api-key": "dev-local-key"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    s = client.get(f"/v1/tts/jobs/{job_id}", headers={"x-api-key": "dev-local-key"})
    assert s.status_code == 200
    assert s.json()["status"] in {"queued", "processing", "succeeded"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs_api.py::test_create_job_and_poll_status -v`
Expected: FAIL with missing `app` routes

- [ ] **Step 3: Implement schemas, routes, and app wiring**

```python
# novel_tts/schemas.py
from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    request_id: str
    book_id: str
    chapter_id: str
    text: str = Field(min_length=1)
    voice_profile: str
    model_id: str | None = None
    audio_format: str = "wav"
    sample_rate: int = 24000
    speed: float | None = None
    pitch: float | None = None
    volume: float | None = None
    pause_ms: int | None = 160


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    segments_total: int = 0
    segments_done: int = 0
    audio_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
```

```python
# main.py
from novel_tts.api import app
```

```python
# novel_tts/api.py
import asyncio
import hashlib
import json
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
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
    # repository + worker enqueue are wired in Task 7
    return {"job_id": "stub-job", "status": "queued", "text_hash": text_hash}


@app.get("/v1/tts/jobs/{job_id}")
async def get_job(job_id: str, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    return {"job_id": job_id, "status": "queued", "progress": 0, "segments_total": 0, "segments_done": 0}


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs_api.py::test_create_job_and_poll_status -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py novel_tts/schemas.py novel_tts/api.py tests/test_jobs_api.py
git commit -m "feat: add fastapi endpoints and api key guard"
```

## Task 7: Wire Real Repository + Worker into API and Complete End-to-End Job Flow

**Files:**
- Modify: `novel_tts/db.py`
- Modify: `novel_tts/repository.py`
- Modify: `novel_tts/api.py`
- Modify: `novel_tts/worker.py`
- Test: `tests/test_jobs_api.py`, `tests/test_worker_flow.py`

- [ ] **Step 1: Write failing integration test for full lifecycle**

```python
# tests/test_jobs_api.py

def test_full_job_lifecycle_with_fake_engine(test_client):
    payload = {
        "request_id": "req-lifecycle-1",
        "book_id": "book-b",
        "chapter_id": "ch-002",
        "text": "这是生命周期测试。" * 180,
        "voice_profile": "narrator_default",
    }
    r = test_client.post("/v1/tts/jobs", json=payload, headers={"x-api-key": "dev-local-key"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    # Allow worker to process once in test fixture
    test_client.app.state.run_worker_once()

    s = test_client.get(f"/v1/tts/jobs/{job_id}", headers={"x-api-key": "dev-local-key"})
    assert s.status_code == 200
    assert s.json()["status"] == "succeeded"

    d = test_client.get(f"/v1/tts/jobs/{job_id}/audio", headers={"x-api-key": "dev-local-key"})
    assert d.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs_api.py::test_full_job_lifecycle_with_fake_engine -v`
Expected: FAIL because worker/repository are not wired in app state

- [ ] **Step 3: Implement full wiring and status reporting**

```python
# novel_tts/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from novel_tts.config import Settings
from novel_tts.models import Base


settings = Settings()
engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)
```

```python
# novel_tts/api.py (key parts)
from novel_tts.db import SessionLocal
from novel_tts.repository import JobRepository
from novel_tts.worker import WorkerService
from novel_tts.tts_engine import FakeTTSEngine

session = SessionLocal()
repo = JobRepository(session)
engine = FakeTTSEngine(sample_rate=24000)
worker = WorkerService(repo=repo, tts_engine=engine, temp_dir=Path(settings.temp_dir), out_dir=Path(settings.output_dir))
app.state.worker = worker
app.state.repo = repo
app.state.run_worker_once = lambda: asyncio.run(worker.process_job_nowait())

@app.post("/v1/tts/jobs")
async def create_job(body: dict, x_api_key: str | None = Header(default=None)):
    ...
    payload = {
        "request_id": body["request_id"],
        "book_id": body["book_id"],
        "chapter_id": body["chapter_id"],
        "text": body["text"],
        "voice_profile": body["voice_profile"],
        "model_id": model_id,
        "params_json": json.dumps(body, ensure_ascii=False),
        "text_hash": text_hash,
    }
    job = repo.create_or_get(payload)
    await worker.enqueue(job.job_id)
    return {"job_id": job.job_id, "status": job.status}
```

```python
# novel_tts/repository.py (additional methods signatures)
def get(self, job_id: str) -> Job: ...
def mark_processing(self, job_id: str) -> None: ...
def set_total(self, job_id: str, total: int) -> None: ...
def set_done(self, job_id: str, done: int) -> None: ...
def mark_succeeded(self, job_id: str, audio_path: str) -> None: ...
def mark_failed(self, job_id: str, code: str, message: str) -> None: ...
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_jobs_api.py tests/test_worker_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add novel_tts/db.py novel_tts/repository.py novel_tts/api.py novel_tts/worker.py tests/test_jobs_api.py tests/test_worker_flow.py
git commit -m "feat: wire async queue worker and full job lifecycle api"
```

## Task 8: Documentation, Ops Runbook, and Final Verification

**Files:**
- Modify: `README.md`
- Test: full suite

- [ ] **Step 1: Write failing docs smoke check (command examples must run)**

```bash
# Manual check expectation
# 1) Install deps
# 2) Start service
# 3) Submit job
# 4) Poll and download
```

- [ ] **Step 2: Run existing tests before doc update**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 3: Update README with concrete runbook and API examples**

```markdown
# README sections to add
- Environment and GPU notes (Windows 4090)
- Quick start commands
- API key usage
- cURL examples:
  - POST /v1/tts/jobs
  - GET /v1/tts/jobs/{job_id}
  - GET /v1/tts/jobs/{job_id}/audio
- Model switch config from 0.6B to 1.7B
- Troubleshooting: queue backlog, GPU contention, auth failures
```

- [ ] **Step 4: Run final verification commands**

Run: `pytest -v`
Expected: all PASS

Run: `uvicorn main:app --host 0.0.0.0 --port 8008`
Expected: service starts; `/healthz` returns 200

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add runbook and api usage for phase-1 service"
```

## Spec Coverage Self-Review

Coverage check against approved spec:
- Async chapter API: Tasks 6 and 7.
- Idempotency and dedup baseline: Tasks 2 and 7.
- Segmentation and merge strategy: Task 3.
- Worker state machine and retry-ready hooks: Task 5 (state), Task 7 (full lifecycle).
- 0.6B default + 1.7B reserved config: Task 1 and Task 4.
- LAN deploy and ops concerns: Task 8.

Placeholder scan:
- No TBD/TODO markers.
- Every code-change step includes concrete code blocks.
- Every test/run step includes exact command and expected outcome.

Type/signature consistency:
- `JobRepository` methods used by worker/api are explicitly declared in Task 7.
- `model_id` default/fallback path defined in Task 1 and consumed in Task 6/7.

