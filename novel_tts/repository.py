# novel_tts/repository.py
from sqlalchemy import select
from novel_tts.models import Job


class JobRepository:
    def __init__(self, session):
        self.session = session

    def create_or_get(self, payload: dict) -> Job:
        stmt = select(Job).where(
            Job.request_id == payload["request_id"],
            Job.chapter_id == payload["chapter_id"]
        )
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

    def get(self, job_id: str) -> Job:
        stmt = select(Job).where(Job.job_id == job_id)
        job = self.session.execute(stmt).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        return job

    def mark_processing(self, job_id: str) -> None:
        job = self.get(job_id)
        job.status = "processing"
        self.session.commit()

    def set_total(self, job_id: str, total: int) -> None:
        job = self.get(job_id)
        job.segments_total = total
        self.session.commit()

    def set_done(self, job_id: str, done: int) -> None:
        job = self.get(job_id)
        job.segments_done = done
        self.session.commit()

    def mark_succeeded(self, job_id: str, audio_path: str) -> None:
        job = self.get(job_id)
        job.status = "succeeded"
        job.audio_path = audio_path
        self.session.commit()

    def mark_failed(self, job_id: str, code: str, message: str) -> None:
        job = self.get(job_id)
        job.status = "failed"
        job.error_code = code
        job.error_message = message
        self.session.commit()
