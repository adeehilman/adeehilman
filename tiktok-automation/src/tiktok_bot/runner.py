"""Command implementations, kept out of the argparse plumbing."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .browser import browser_context, is_logged_in
from .config import Selectors, Settings, load_skip_list
from .messenger import Outcome, SendResult, send_sticker
from .pacing import Pacer
from .scraper import Account, scrape_following
from .session import describe_session, load_storage_state
from .state import SentLog

log = logging.getLogger(__name__)


def _selectors(settings: Settings) -> Selectors:
    return Selectors.load(settings.selectors_file)


def check(settings: Settings) -> int:
    """Verify the stored session still logs in. Cheap smoke test for CI."""
    state = load_storage_state(settings)
    log.info("session: %s", describe_session(state))
    selectors = _selectors(settings)
    with browser_context(settings, state) as (_browser, _context, page):
        if is_logged_in(page, selectors):
            log.info("session is valid — logged in as @%s", settings.username or "?")
            return 0
    log.error("session looks logged out; re-run scripts/capture_session.py")
    return 1


def scrape(settings: Settings, limit: int = 0) -> int:
    username = settings.require_username()
    state = load_storage_state(settings)
    selectors = _selectors(settings)

    with browser_context(settings, state) as (_browser, _context, page):
        if not is_logged_in(page, selectors):
            log.error("session is logged out; nothing scraped")
            return 1
        accounts = scrape_following(page, selectors, username, limit=limit)

    settings.following_file.parent.mkdir(parents=True, exist_ok=True)
    settings.following_file.write_text(
        json.dumps([account.to_dict() for account in accounts], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("wrote %d account(s) to %s", len(accounts), settings.following_file)
    return 0


def load_following(settings: Settings) -> list[Account]:
    path: Path = settings.following_file
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("could not read %s (%s)", path, exc)
        return []
    return [
        Account(handle=str(item["handle"]).lower(), nickname=item.get("nickname", ""))
        for item in payload
        if isinstance(item, dict) and item.get("handle")
    ]


def select_targets(
    accounts: list[Account],
    settings: Settings,
    sent_log: SentLog,
    only: list[str] | None = None,
) -> list[Account]:
    """Apply every filter that does not need a browser, in a fixed order.

    Order matters for the log: an explicit --only list narrows first, then the
    skip list, then the cooldown, and the run budget truncates whatever is left.
    """
    skip = load_skip_list(settings.skip_list_file)
    selected: list[Account] = []

    if only:
        wanted = {handle.strip().lstrip("@").lower() for handle in only if handle.strip()}
        known = {account.handle: account for account in accounts}
        accounts = [known.get(handle, Account(handle=handle)) for handle in sorted(wanted)]

    for account in accounts:
        if account.handle in skip:
            log.info("skipping @%s: on the skip list", account.handle)
            continue
        if sent_log.in_cooldown(account.handle, settings.resend_cooldown_days):
            log.info(
                "skipping @%s: messaged within the last %d day(s)",
                account.handle,
                settings.resend_cooldown_days,
            )
            continue
        selected.append(account)

    if settings.max_messages and len(selected) > settings.max_messages:
        log.info(
            "%d eligible account(s); trimming to the per-run cap of %d",
            len(selected),
            settings.max_messages,
        )
        selected = selected[: settings.max_messages]
    return selected


def send(settings: Settings, only: list[str] | None = None, rescrape: bool = False) -> int:
    username = settings.require_username()
    state = load_storage_state(settings)
    selectors = _selectors(settings)
    sent_log = SentLog.load(settings.state_file)

    if settings.sending_enabled:
        log.warning("SENDING IS LIVE: up to %d message(s) will go out", settings.max_messages)
    else:
        log.info(
            "dry-run (DRY_RUN=%s, ALLOW_SEND=%s): the browser walks the whole "
            "flow but types nothing",
            settings.dry_run,
            settings.allow_send,
        )

    results: list[SendResult] = []
    pacer = Pacer(settings.min_delay_seconds, settings.max_delay_seconds, settings.max_messages)

    with browser_context(settings, state) as (_browser, _context, page):
        if not is_logged_in(page, selectors):
            log.error("session is logged out; nothing sent")
            return 1

        accounts = load_following(settings)
        if rescrape or not accounts:
            log.info("scraping the following list")
            accounts = scrape_following(page, selectors, username)

        targets = select_targets(accounts, settings, sent_log, only=only)
        if not targets:
            log.info("nothing to do: no account passed the filters")
            return 0

        log.info("%d target(s) this run", len(targets))

        for index, account in enumerate(targets):
            if pacer.exhausted():
                log.info("per-run cap reached; stopping")
                break

            result = send_sticker(page, selectors, settings, account.handle, pacer)
            results.append(result)

            if result.outcome.counts_against_budget:
                pacer.consume()
                sent_log.record(
                    account.handle,
                    result.detail or settings.sticker_emoji,
                    settings.message_mode,
                    dry_run=not settings.sending_enabled,
                )
                sent_log.save()

            if index < len(targets) - 1 and not pacer.exhausted():
                pacer.wait()

    _report(results)
    return 0 if all(result.outcome is not Outcome.FAILED for result in results) else 1


def _report(results: list[SendResult]) -> None:
    tally: dict[str, int] = {}
    for result in results:
        tally[result.outcome.value] = tally.get(result.outcome.value, 0) + 1
    log.info("run summary: %s", tally or "nothing attempted")
    for result in results:
        if result.outcome is Outcome.FAILED:
            log.error("failed: @%s (%s)", result.handle, result.detail)


def status(settings: Settings) -> int:
    sent_log = SentLog.load(settings.state_file)
    summary = sent_log.summary()
    log.info("sent-log %s: %s", settings.state_file, summary)
    for handle, record in sorted(
        sent_log.records.items(), key=lambda item: item[1].get("sent_at", ""), reverse=True
    )[:20]:
        marker = "dry-run" if record.get("dry_run") else "sent"
        log.info("  @%-24s %s  %s  %s", handle, record.get("sent_at", "?"), marker, record.get("payload", ""))
    return 0
