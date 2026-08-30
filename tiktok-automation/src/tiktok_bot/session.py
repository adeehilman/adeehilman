"""Loading and storing the Playwright storage_state that stands in for login.

There is no password anywhere in this project. You log in by hand once, in a
real browser window (`scripts/capture_session.py`), and what gets persisted is
the same cookie jar your browser already holds. Treat the resulting file as a
credential: anyone holding it is logged in as you.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from pathlib import Path
from typing import Any

from .config import ConfigError, Settings

log = logging.getLogger(__name__)

TIKTOK_COOKIE_HINTS = ("sessionid", "sessionid_ss", "sid_tt")


class SessionError(RuntimeError):
    """Raised when no usable session is available."""


def load_storage_state(settings: Settings) -> dict[str, Any]:
    """Return the storage_state dict, preferring the file over the env blob."""
    if settings.session_file and settings.session_file.exists():
        log.info("using session file %s", settings.session_file)
        return _parse(settings.session_file.read_text(encoding="utf-8"))

    if settings.session_b64:
        log.info("using session from TIKTOK_SESSION_B64")
        try:
            raw = base64.b64decode(settings.session_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise SessionError("TIKTOK_SESSION_B64 is not valid base64") from exc
        return _parse(raw.decode("utf-8"))

    raise SessionError(
        "no session available: run scripts/capture_session.py locally, then set "
        "TIKTOK_SESSION_FILE or the TIKTOK_SESSION_B64 secret"
    )


def _parse(text: str) -> dict[str, Any]:
    try:
        state = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SessionError("session payload is not valid JSON") from exc
    if not isinstance(state, dict) or "cookies" not in state:
        raise SessionError("session payload is not a Playwright storage_state")
    if not describe_session(state)["has_auth_cookie"]:
        log.warning(
            "session has no recognisable TikTok auth cookie — it will probably "
            "be treated as logged out"
        )
    return state


def describe_session(state: dict[str, Any]) -> dict[str, Any]:
    """Non-sensitive summary: counts and flags only, never cookie values."""
    cookies = state.get("cookies") or []
    names = {cookie.get("name", "") for cookie in cookies}
    return {
        "cookie_count": len(cookies),
        "origins": len(state.get("origins") or []),
        "has_auth_cookie": any(hint in names for hint in TIKTOK_COOKIE_HINTS),
    }


def write_storage_state(state: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:  # e.g. a filesystem that does not carry POSIX modes
        log.debug("could not tighten permissions on %s", path)
    return path


def encode_for_secret(path: Path) -> str:
    """base64 of a session file, ready to paste into a repository secret."""
    if not path.exists():
        raise ConfigError(f"session file not found: {path}")
    return base64.b64encode(path.read_bytes()).decode("ascii")
