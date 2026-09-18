"""Runtime configuration, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

try:  # optional dependency, the app works without it
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:  # pragma: no cover
    pass


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    elevenlabs_api_key: str | None = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY"))
    elevenlabs_agent_id: str | None = field(
        default_factory=lambda: os.getenv("ELEVENLABS_AGENT_ID")
    )
    enable_pr: bool = field(default_factory=lambda: _flag("DEVPROD_ENABLE_PR", default=True))
    pr_base_branch: str = field(default_factory=lambda: os.getenv("DEVPROD_PR_BASE", ""))
    repo_root: Path = REPO_ROOT
    logs_dir: Path = REPO_ROOT / "var" / "logs"
    docs_dir: Path = REPO_ROOT / "documentation" / "incidents"
    developer_name: str = field(default_factory=lambda: os.getenv("DEVPROD_DEVELOPER", "developer"))

    @property
    def voice_mode(self) -> str:
        """'live' when an ElevenLabs agent is configured, else 'mock' (browser TTS)."""
        return "live" if self.elevenlabs_api_key and self.elevenlabs_agent_id else "mock"


settings = Settings()
settings.logs_dir.mkdir(parents=True, exist_ok=True)
settings.docs_dir.mkdir(parents=True, exist_ok=True)
