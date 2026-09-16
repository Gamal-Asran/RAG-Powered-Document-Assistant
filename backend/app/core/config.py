from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_ROOT / ".env", REPOSITORY_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NIST AI Risk Assistant"
    app_env: str = "development"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    ollama_context: int = Field(default=4096, gt=0)
    ollama_temperature: float = 0.1
    ollama_num_predict: int = Field(default=1024, gt=0)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    chroma_path: Path = Path("backend/data/vector_store")
    chroma_collection: str = "nist_ai_risk_corpus"
    retrieval_top_k: int = Field(default=4, gt=0)
    max_history_exchanges: int = Field(default=2, ge=0)
    cors_origins: str = (
        "http://localhost:8501,http://127.0.0.1:8501,"
        "http://localhost:7860,http://127.0.0.1:7860"
    )

    @field_validator("embedding_device")
    @classmethod
    def cpu_only(cls, value: str) -> str:
        if value != "cpu":
            raise ValueError("EMBEDDING_DEVICE must be exactly 'cpu'")
        return value

    @field_validator("ollama_model", "chroma_collection", "embedding_model")
    @classmethod
    def non_empty_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("model and collection names must be non-empty")
        return value

    @field_validator("chroma_path")
    @classmethod
    def resolve_existing_chroma_path(cls, value: Path) -> Path:
        resolved = value if value.is_absolute() else REPOSITORY_ROOT / value
        resolved = resolved.resolve()
        if not resolved.is_dir():
            raise ValueError(f"vector-store directory does not exist: {resolved}")
        return resolved

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
