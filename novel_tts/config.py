from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelInfo(BaseModel):
    hf_repo: str
    enabled: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOVEL_TTS_")

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
            hf_repo="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            enabled=True,
        ),
        "qwen3_tts_1_7b_customvoice": ModelInfo(
            hf_repo="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            enabled=False,
        ),
    }
    max_concurrent_jobs: int = 1
    request_body_max_chars: int = 10000

    @model_validator(mode='after')
    def validate_model_consistency(self) -> 'Settings':
        registry_keys = set(self.model_registry.keys())
        unknown = set(self.available_models) - registry_keys
        if unknown:
            raise ValueError(f"available_models contains IDs not in model_registry: {unknown}")
        if self.default_model_id not in registry_keys:
            raise ValueError(f"default_model_id '{self.default_model_id}' not in model_registry")
        return self
