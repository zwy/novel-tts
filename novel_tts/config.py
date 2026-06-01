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
