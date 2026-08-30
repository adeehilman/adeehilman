"""Sending one sticker to one account, through the normal web chat UI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from playwright.sync_api import Page

from .browser import BASE_URL, find, require
from .config import Selectors, Settings
from .pacing import Pacer
from .scraper import is_followed_by_me

log = logging.getLogger(__name__)


class Outcome(str, Enum):
    SENT = "sent"
    DRY_RUN = "dry_run"
    SKIPPED_NOT_FOLLOWED = "skipped_not_followed"
    SKIPPED_NO_MESSAGE_BUTTON = "skipped_no_message_button"
    FAILED = "failed"

    @property
    def counts_against_budget(self) -> bool:
        return self in {Outcome.SENT, Outcome.DRY_RUN}


@dataclass
class SendResult:
    handle: str
    outcome: Outcome
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome in {Outcome.SENT, Outcome.DRY_RUN}


def send_sticker(
    page: Page,
    selectors: Selectors,
    settings: Settings,
    handle: str,
    pacer: Pacer,
) -> SendResult:
    """Open `handle`'s profile and send the configured sticker.

    Every path checks two things first: that we actually follow the account,
    and that sending is switched on. In dry-run the browser still walks up to
    the chat box, so a rehearsal exercises the same selectors a real send does
    — it just never types anything.
    """
    log.info("--- @%s", handle)
    page.goto(f"{BASE_URL}/@{handle}", wait_until="domcontentloaded")
    page.wait_for_timeout(2_500)

    if not is_followed_by_me(page, selectors):
        log.info("skipping @%s: not in your following list", handle)
        return SendResult(handle, Outcome.SKIPPED_NOT_FOLLOWED)

    message_button = find(page, selectors, "profile.message_button", timeout_ms=10_000)
    if message_button is None:
        log.info("skipping @%s: no message button (their DMs are likely closed)", handle)
        return SendResult(handle, Outcome.SKIPPED_NO_MESSAGE_BUTTON)

    try:
        message_button.click()
        pacer.jitter(1.5, 2.0)
        chat_input = require(page, selectors, "messaging.chat_input", timeout_ms=20_000)
    except Exception as exc:  # selector rot, a modal, a rate-limit interstitial
        log.error("could not open the chat with @%s: %s", handle, exc)
        return SendResult(handle, Outcome.FAILED, str(exc))

    payload = _payload_description(settings)

    if not settings.sending_enabled:
        log.info("[dry-run] would send %s to @%s", payload, handle)
        return SendResult(handle, Outcome.DRY_RUN, payload)

    try:
        if settings.message_mode == "sticker":
            _send_from_sticker_panel(page, selectors, settings, pacer)
        else:
            _send_emoji(page, selectors, settings, chat_input, pacer)
    except Exception as exc:
        log.error("send to @%s failed: %s", handle, exc)
        return SendResult(handle, Outcome.FAILED, str(exc))

    page.wait_for_timeout(2_000)
    log.info("sent %s to @%s", payload, handle)
    return SendResult(handle, Outcome.SENT, payload)


def _payload_description(settings: Settings) -> str:
    if settings.message_mode == "sticker":
        return f"sticker #{settings.sticker_index}"
    return settings.sticker_emoji


def _send_emoji(page: Page, selectors: Selectors, settings: Settings, chat_input, pacer: Pacer) -> None:
    chat_input.click()
    pacer.jitter(0.4, 0.6)
    # fill() does not fire the input events TikTok's editor listens for.
    chat_input.type(settings.sticker_emoji, delay=80)
    pacer.jitter(0.5, 0.8)
    _submit(page, selectors)


def _send_from_sticker_panel(page: Page, selectors: Selectors, settings: Settings, pacer: Pacer) -> None:
    require(page, selectors, "messaging.sticker_toggle", timeout_ms=10_000).click()
    pacer.jitter(1.0, 1.0)
    panel = require(page, selectors, "messaging.sticker_panel", timeout_ms=10_000)

    items = None
    for candidate in selectors.get("messaging.sticker_item"):
        located = panel.locator(candidate)
        if located.count():
            items = located
            break
    if items is None or not items.count():
        raise LookupError("sticker panel opened but contained no selectable items")

    index = min(settings.sticker_index, items.count() - 1)
    items.nth(index).click()
    pacer.jitter(0.6, 0.8)

    # Some builds post the sticker straight from the panel; a send button is
    # only there when it does not, so a missing one is not an error.
    send_button = find(page, selectors, "messaging.send_button", timeout_ms=3_000)
    if send_button is not None:
        try:
            send_button.click()
        except Exception:
            log.debug("send button present but not clickable; sticker likely already posted")


def _submit(page: Page, selectors: Selectors) -> None:
    send_button = find(page, selectors, "messaging.send_button", timeout_ms=3_000)
    if send_button is not None:
        send_button.click()
        return
    page.keyboard.press("Enter")
