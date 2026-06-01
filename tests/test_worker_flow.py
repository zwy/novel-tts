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
