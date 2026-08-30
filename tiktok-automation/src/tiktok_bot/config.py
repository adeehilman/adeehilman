"""Configuration loading: environment variables plus the YAML selector map."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent

DEFAULT_SELECTORS = PROJECT_ROOT / "config" / "selectors.yml"
DEFAULT_SKIP_LIST = PROJECT_ROOT / "config" / "skip_list.txt"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


class ConfigError(RuntimeError):
    """Raised when the environment is not usable for the requested command."""


@dataclass
class Settings:
    username: str = ""
    session_file: Path = Path("storage_state.json")
    session_b64: str = ""

    dry_run: bool = True
    allow_send: bool = False
    max_messages: int = 5
    min_delay_seconds: int = 45
    max_delay_seconds: int = 120
    resend_cooldown_days: int = 30

    message_mode: str = "emoji"
    sticker_emoji: str = "🎉"
    sticker_index: int = 0

    headless: bool = True
    state_file: Path = PROJECT_ROOT / "state" / "sent.json"
    following_file: Path = PROJECT_ROOT / "out" / "following.json"
    selectors_file: Path = DEFAULT_SELECTORS
    skip_list_file: Path = DEFAULT_SKIP_LIST

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            username=os.getenv("TIKTOK_USERNAME", "").strip().lstrip("@"),
            session_file=Path(os.getenv("TIKTOK_SESSION_FILE", "storage_state.json")),
            session_b64=os.getenv("TIKTOK_SESSION_B64", "").strip(),
            dry_run=_env_bool("DRY_RUN", True),
            allow_send=_env_bool("ALLOW_SEND", False),
            max_messages=_env_int("MAX_MESSAGES", 5),
            min_delay_seconds=_env_int("MIN_DELAY_SECONDS", 45),
            max_delay_seconds=_env_int("MAX_DELAY_SECONDS", 120),
            resend_cooldown_days=_env_int("RESEND_COOLDOWN_DAYS", 30),
            message_mode=os.getenv("MESSAGE_MODE", "emoji").strip().lower(),
            sticker_emoji=os.getenv("STICKER_EMOJI", "🎉"),
            sticker_index=_env_int("STICKER_INDEX", 0),
            headless=_env_bool("HEADLESS", True),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.message_mode not in {"emoji", "sticker"}:
            raise ConfigError(
                f"MESSAGE_MODE must be 'emoji' or 'sticker', got {self.message_mode!r}"
            )
        if self.max_messages < 0:
            raise ConfigError("MAX_MESSAGES cannot be negative")
        if self.min_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ConfigError("delay bounds cannot be negative")
        if self.min_delay_seconds > self.max_delay_seconds:
            raise ConfigError("MIN_DELAY_SECONDS must not exceed MAX_DELAY_SECONDS")

    @property
    def sending_enabled(self) -> bool:
        """Both switches must be thrown before a single message goes out."""
        return self.allow_send and not self.dry_run

    def require_username(self) -> str:
        if not self.username:
            raise ConfigError("TIKTOK_USERNAME is not set")
        return self.username


@dataclass
class Selectors:
    """The selector map, with `first_that_matches` semantics per entry."""

    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Selectors":
        if not path.exists():
            raise ConfigError(f"selector file not found: {path}")
        with path.open(encoding="utf-8") as handle:
            return cls(yaml.safe_load(handle) or {})

    def get(self, dotted_key: str) -> list[str]:
        node: Any = self.data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise ConfigError(f"selector {dotted_key!r} missing from selectors.yml")
            node = node[part]
        if isinstance(node, str):
            return [node]
        if isinstance(node, list) and all(isinstance(item, str) for item in node):
            return list(node)
        raise ConfigError(f"selector {dotted_key!r} must be a string or list of strings")


def load_skip_list(path: Path) -> set[str]:
    """Handles that must never be messaged, normalised to lowercase, no '@'."""
    if not path.exists():
        return set()
    handles = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip().lstrip("@").lower()
        if entry:
            handles.add(entry)
    return handles
