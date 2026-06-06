from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    vault_dir: Path
    bind_host: str
    bind_port: int
    api_token: str | None
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str
    min_archive_content_length: int = 100
    max_archive_content_bytes: int = 1_000_000

    @property
    def requires_auth(self) -> bool:
        return bool(self.api_token)


def load_settings() -> Settings:
    return Settings(
        vault_dir=Path(os.environ.get("ARCH0_VAULT_DIR", "arch-vault")),
        bind_host=os.environ.get("ARCH0_HOST", "127.0.0.1"),
        bind_port=int(os.environ.get("ARCH0_PORT", "8000")),
        api_token=os.environ.get("ARCH0_API_TOKEN"),
        llm_api_key=os.environ.get("ARCH0_LLM_API_KEY"),
        llm_base_url=os.environ.get("ARCH0_LLM_BASE_URL", "https://api.openai.com/v1"),
        llm_model=os.environ.get("ARCH0_LLM_MODEL", "gpt-4.1-mini"),
    )
