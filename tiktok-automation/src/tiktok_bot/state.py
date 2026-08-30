"""The sent-log.

This is what stops the tool turning into a spammer across runs: an account
that was messaged stays off the list until the cooldown expires, even if the
job is triggered ten times in an afternoon.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class SentLog:
    path: Path
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "SentLog":
        if not path.exists():
            return cls(path=path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("sent-log at %s unreadable (%s); starting empty", path, exc)
            return cls(path=path)
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, dict):
            log.warning("sent-log at %s has an unexpected shape; starting empty", path)
            return cls(path=path)
        return cls(path=path, records=records)

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": SCHEMA_VERSION,
            "updated_at": _utcnow().isoformat(),
            "records": self.records,
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.path

    def last_sent_at(self, handle: str) -> datetime | None:
        record = self.records.get(handle.lower())
        if not record:
            return None
        return _parse_ts(record.get("sent_at", ""))

    def in_cooldown(self, handle: str, cooldown_days: int) -> bool:
        last = self.last_sent_at(handle)
        if last is None:
            return False
        return _utcnow() - last < timedelta(days=cooldown_days)

    def record(self, handle: str, payload: str, mode: str, dry_run: bool) -> None:
        self.records[handle.lower()] = {
            "handle": handle,
            "sent_at": _utcnow().isoformat(),
            "payload": payload,
            "mode": mode,
            "dry_run": dry_run,
        }

    def summary(self) -> dict[str, int]:
        real = sum(1 for r in self.records.values() if not r.get("dry_run"))
        return {
            "total": len(self.records),
            "sent": real,
            "dry_run": len(self.records) - real,
        }
