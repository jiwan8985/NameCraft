"""애플리케이션 설정.

유료 AI API 키(Anthropic/Gemini 등)는 설정 항목으로 존재하지 않는다 (기획서 §33.1, §33.4).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NAMECRAFT_", env_file=".env", extra="ignore")

    env: str = "local"
    var_dir: Path = REPO_ROOT / "var"
    database_url: str | None = None  # 기본: var_dir/namecraft.db (SQLite)
    token_file: Path | None = None  # 기본: var_dir/local_token
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    data_version: str = "unreleased"  # Phase 2에서 data_release_versions와 연동
    ollama_url: str = "http://127.0.0.1:11434"  # 로컬 Ollama (원격 주소 사용 금지 — §33.1)

    @field_validator("ollama_url")
    @classmethod
    def _local_only(cls, v: str) -> str:
        from urllib.parse import urlparse

        host = urlparse(v).hostname
        if host not in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}:
            raise ValueError("ollama_url 은 로컬 주소만 허용합니다(원격 모델 호출 금지).")
        return v.rstrip("/")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.var_dir / 'namecraft.db').as_posix()}"

    @property
    def resolved_token_file(self) -> Path:
        return self.token_file or (self.var_dir / "local_token")


@lru_cache
def get_settings() -> Settings:
    return Settings()
