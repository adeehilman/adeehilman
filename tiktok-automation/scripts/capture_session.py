#!/usr/bin/env python3
"""Log in to TikTok by hand, once, and save the resulting session.

Run this on your own machine — it needs a visible browser window. It opens
TikTok, waits while *you* type your credentials and clear any captcha or 2FA,
and then writes the cookie jar to storage_state.json.

    python scripts/capture_session.py
    python -m tiktok_bot encode-session   # base64, for the CI secret

The script never sees or stores your password: everything is typed into the
browser by you. The file it produces is still a credential — it is enough to
act as you on TikTok. Keep it out of git (it is in .gitignore) and put it in
GitHub as an encrypted secret, nothing else.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from tiktok_bot.config import Selectors, Settings  # noqa: E402
from tiktok_bot.logging_setup import setup_logging  # noqa: E402
from tiktok_bot.session import describe_session, write_storage_state  # noqa: E402

LOGIN_URL = "https://www.tiktok.com/login"
POLL_INTERVAL_MS = 3_000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="storage_state.json", help="where to write the session")
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait for login")
    args = parser.parse_args()

    log = setup_logging()
    settings = Settings.from_env()
    selectors = Selectors.load(settings.selectors_file)
    markers = selectors.get("login.logged_in_marker")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
        page = context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        log.info("A browser window is open. Log in there — take as long as you need.")
        log.info("Waiting up to %d seconds for the session to appear...", args.timeout)

        deadline_polls = max(1, (args.timeout * 1_000) // POLL_INTERVAL_MS)
        for _ in range(deadline_polls):
            if any(page.locator(marker).first.count() for marker in markers):
                break
            page.wait_for_timeout(POLL_INTERVAL_MS)
        else:
            log.error("still not logged in after %ds — nothing was saved", args.timeout)
            context.close()
            browser.close()
            return 1

        page.wait_for_timeout(2_000)
        state = context.storage_state()
        context.close()
        browser.close()

    path = write_storage_state(state, Path(args.output))
    log.info("saved %s (%s)", path, describe_session(state))
    log.info("next: python -m tiktok_bot check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
