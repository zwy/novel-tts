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
    speed: float | None = Field(default=None, ge=0.1, le=3.0)
    pitch: float | None = Field(default=None, ge=0.1, le=3.0)
    volume: float | None = Field(default=None, ge=0.1, le=3.0)
    pause_ms: int | None = 160
    instruct: str | None = Field(default=None, description="Natural-language style/emotion instruction, e.g. '用温柔悲伤的语气朗读'.")


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    segments_total: int = 0
    segments_done: int = 0
    audio_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
