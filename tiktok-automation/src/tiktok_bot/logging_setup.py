"""Console logging that stays readable inside a GitHub Actions log."""

from __future__ import annotations

import logging
import os
import sys


def setup_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    root.addHandler(handler)

    # Playwright is chatty at DEBUG and drowns out everything else.
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    return logging.getLogger("tiktok_bot")


def redact(text: str) -> str:
    """Strip anything that looks like the session blob out of a log line."""
    secret = os.getenv("TIKTOK_SESSION_B64", "")
    if secret and len(secret) > 8:
        text = text.replace(secret, "<session redacted>")
    return text
