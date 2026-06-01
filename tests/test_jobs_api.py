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


def test_reject_missing_api_key():
    client = TestClient(app)
    payload = {
        "request_id": "req-noauth",
        "book_id": "book-a",
        "chapter_id": "ch-noauth",
        "text": "测试无密钥请求。",
        "voice_profile": "narrator_default",
    }
    r = client.post("/v1/tts/jobs", json=payload)
    assert r.status_code == 401


def test_list_models():
    client = TestClient(app)
    r = client.get("/v1/models", headers={"x-api-key": "dev-local-key"})
    assert r.status_code == 200
    data = r.json()
    assert "default_model_id" in data
    assert "models" in data


def test_healthz():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


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
    assert job_id != "stub-job"  # must be a real UUID

    # Synchronously process one job from the queue
    import asyncio
    asyncio.run(test_client.app.state.worker.process_job(job_id))

    s = test_client.get(f"/v1/tts/jobs/{job_id}", headers={"x-api-key": "dev-local-key"})
    assert s.status_code == 200
    assert s.json()["status"] == "succeeded"

    d = test_client.get(f"/v1/tts/jobs/{job_id}/audio", headers={"x-api-key": "dev-local-key"})
    assert d.status_code == 200
