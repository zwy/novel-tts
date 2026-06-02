from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelInfo(BaseModel):
    hf_repo: str
    enabled: bool = True
    model_type: str = "customvoice"
    #: "qwen" for local Qwen3-TTS, "mimo" for Xiaomi mimo HTTP TTS.
    provider: str = "qwen"
    #: Provider-specific configuration. For non-HF providers (e.g. mimo) this
    #: carries the upstream model id and endpoint instead of a HF repo name.
    provider_config: dict = {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOVEL_TTS_")

    api_key: str = "dev-local-key"
    host: str = "0.0.0.0"
    port: int = 8008
    db_url: str = "sqlite:///./novel_tts.db"
    output_dir: str = "./data/audio"
    temp_dir: str = "./data/temp"
    default_model_id: str = "qwen3_tts_0_6b_customvoice"
    #: Models the API will accept on `POST /v1/tts/jobs`. Defaults to everything
    #: that is `enabled=True` in the registry; override via
    #: `NOVEL_TTS_AVAILABLE_MODELS` to opt in/out without code changes.
    available_models: list[str] = [
        "qwen3_tts_0_6b_customvoice",
        "mimo_v2_5_tts",
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
        # Cloud provider: Xiaomi mimo TTS v2.5 (preset voices only).
        # enabled=True by default so a configured MIMO_API_KEY is enough to route jobs
        # to the cloud engine; flip to False (or override via env) to opt out.
        # `hf_repo` is left blank — mimo is not on HuggingFace — the actual
        # upstream model id lives in `provider_config["model"]` below.
        "mimo_v2_5_tts": ModelInfo(
            hf_repo="",
            enabled=True,
            provider="mimo",
            provider_config={
                "api_base": "https://api.xiaomimimo.com/v1",
                "model": "mimo-v2.5-tts",
            },
        ),
    }
    max_concurrent_jobs: int = 1
    request_body_max_chars: int = 10000
    use_fake_engine: bool = False
    use_flash_attention2: bool = False
    #: API key for the Xiaomi mimo cloud TTS provider. Empty string disables mimo.
    mimo_api_key: str = ""

    @model_validator(mode='after')
    def validate_model_consistency(self) -> 'Settings':
        registry_keys = set(self.model_registry.keys())
        unknown = set(self.available_models) - registry_keys
        if unknown:
            raise ValueError(f"available_models contains IDs not in model_registry: {unknown}")
        if self.default_model_id not in registry_keys:
            raise ValueError(f"default_model_id '{self.default_model_id}' not in model_registry")
        for mid, info in self.model_registry.items():
            if info.provider not in {"qwen", "mimo"}:
                raise ValueError(f"model '{mid}' has unknown provider '{info.provider}'")
        return self
