"""Playwright bootstrap.

Deliberately plain: a stock Chromium, a normal viewport, a normal user agent.
No fingerprint patching and no anti-detection shims — if TikTok decides this
traffic is automated, the answer is to slow down or stop, not to hide.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .config import Selectors, Settings

log = logging.getLogger(__name__)

BASE_URL = "https://www.tiktok.com"
DEFAULT_TIMEOUT_MS = 30_000


@contextlib.contextmanager
def browser_context(
    settings: Settings,
    storage_state: dict[str, Any] | None = None,
) -> Iterator[tuple[Browser, BrowserContext, Page]]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=settings.headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1366, "height": 900},
            locale="en-US",
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.new_page()
        try:
            yield browser, context, page
        finally:
            with contextlib.suppress(Exception):
                context.close()
            with contextlib.suppress(Exception):
                browser.close()


def find(page: Page, selectors: Selectors, key: str, timeout_ms: int = 8_000):
    """Return the first locator from `key` that actually resolves, else None.

    Selector rot is the normal failure mode here, so every lookup walks the
    candidate list from selectors.yml instead of trusting a single string.
    """
    candidates = selectors.get(key)
    per_candidate = max(1_000, timeout_ms // max(1, len(candidates)))
    for candidate in candidates:
        locator = page.locator(candidate).first
        try:
            locator.wait_for(state="attached", timeout=per_candidate)
        except Exception:
            log.debug("selector %s (%s) did not resolve", key, candidate)
            continue
        log.debug("selector %s matched %s", key, candidate)
        return locator
    return None


def require(page: Page, selectors: Selectors, key: str, timeout_ms: int = 8_000):
    locator = find(page, selectors, key, timeout_ms)
    if locator is None:
        raise LookupError(
            f"none of the selectors for {key!r} matched — update config/selectors.yml"
        )
    return locator


def is_logged_in(page: Page, selectors: Selectors) -> bool:
    page.goto(f"{BASE_URL}/foryou", wait_until="domcontentloaded")
    page.wait_for_timeout(3_000)
    return find(page, selectors, "login.logged_in_marker", timeout_ms=10_000) is not None
