"""Scraping the accounts you follow, from your own profile page.

Scope is deliberately narrow: your own following list, and the public header of
a profile you are about to message. Nothing here crawls strangers' followers or
harvests contact details.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

from playwright.sync_api import Page

from .browser import BASE_URL, find, require
from .config import Selectors

log = logging.getLogger(__name__)

HANDLE_RE = re.compile(r"^/@([^/?#]+)")


@dataclass(frozen=True)
class Account:
    handle: str
    nickname: str = ""

    @property
    def profile_url(self) -> str:
        return f"{BASE_URL}/@{self.handle}"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "profile_url": self.profile_url}


def _handle_from_href(href: str | None) -> str | None:
    if not href:
        return None
    path = href.replace(BASE_URL, "", 1)
    match = HANDLE_RE.match(path)
    return match.group(1).lower() if match else None


def open_following_modal(page: Page, selectors: Selectors, username: str) -> None:
    page.goto(f"{BASE_URL}/@{username}", wait_until="domcontentloaded")
    page.wait_for_timeout(3_000)
    require(page, selectors, "following_list.tab_button", timeout_ms=15_000).click()
    require(page, selectors, "following_list.modal", timeout_ms=15_000)
    page.wait_for_timeout(2_000)


def scrape_following(
    page: Page,
    selectors: Selectors,
    username: str,
    limit: int = 0,
    max_scrolls: int = 60,
) -> list[Account]:
    """Return the accounts `username` follows.

    `limit` of 0 means "everything the modal will give up". The scroll loop
    stops early once a pass adds nothing new, which is the normal end state.
    """
    open_following_modal(page, selectors, username)
    modal = require(page, selectors, "following_list.modal", timeout_ms=15_000)
    item_selectors = selectors.get("following_list.user_item")
    link_selector = selectors.get("following_list.user_link")[0]

    found: dict[str, Account] = {}
    stagnant_passes = 0

    for pass_number in range(1, max_scrolls + 1):
        before = len(found)

        for item_selector in item_selectors:
            cards = modal.locator(item_selector)
            for index in range(cards.count()):
                card = cards.nth(index)
                try:
                    href = card.locator(link_selector).first.get_attribute("href")
                except Exception:
                    continue
                handle = _handle_from_href(href)
                if not handle or handle in found:
                    continue
                found[handle] = Account(handle=handle, nickname=_nickname(card, selectors))
            if cards.count():
                # The first selector that returned rows is the right one; the
                # rest are fallbacks and would only produce duplicates.
                break

        log.info("scroll pass %d: %d account(s) collected", pass_number, len(found))

        if limit and len(found) >= limit:
            break

        stagnant_passes = stagnant_passes + 1 if len(found) == before else 0
        if stagnant_passes >= 3:
            log.info("no new accounts across 3 passes — assuming the list is complete")
            break

        modal.evaluate("node => node.scrollBy(0, node.scrollHeight)")
        page.wait_for_timeout(1_500)

    accounts = list(found.values())
    return accounts[:limit] if limit else accounts


def _nickname(card, selectors: Selectors) -> str:
    for candidate in selectors.get("following_list.nickname"):
        try:
            locator = card.locator(candidate).first
            if locator.count():
                return (locator.inner_text() or "").strip()
        except Exception:
            continue
    return ""


def is_followed_by_me(page: Page, selectors: Selectors) -> bool:
    """Read the follow button on the profile page currently open.

    Used as a guard right before messaging: if the button offers "Follow", the
    account is not one we follow and gets skipped.
    """
    button = find(page, selectors, "profile.follow_button", timeout_ms=10_000)
    if button is None:
        log.warning("follow button not found; treating the account as not followed")
        return False
    try:
        label = (button.inner_text() or "").strip().lower()
    except Exception:
        return False
    labels = [item.lower() for item in selectors.get("profile.following_labels")]
    log.debug("follow button reads %r", label)
    return any(item in label for item in labels)
