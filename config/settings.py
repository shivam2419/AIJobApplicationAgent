from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _configured_path(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str
    gmail_credentials_file: Path
    gmail_token_file: Path
    gmail_expected_sender: str
    database_path: Path
    output_dir: Path
    log_level: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
            or "openai/gpt-oss-120b",
            gmail_credentials_file=_configured_path(
                "GMAIL_CREDENTIALS_FILE", "credentials.json"
            ),
            gmail_token_file=_configured_path("GMAIL_TOKEN_FILE", "token.json"),
            gmail_expected_sender=os.getenv(
                "GMAIL_EXPECTED_SENDER", "officialshivam2419@gmail.com"
            ).strip().lower(),
            database_path=_configured_path(
                "DATABASE_PATH", "data/applications.db"
            ),
            output_dir=_configured_path("OUTPUT_DIR", "output"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


settings = Settings.load()
