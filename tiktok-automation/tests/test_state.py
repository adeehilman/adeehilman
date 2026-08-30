from datetime import datetime, timedelta, timezone

from tiktok_bot.state import SentLog


def test_empty_log_for_missing_file(tmp_path):
    log = SentLog.load(tmp_path / "nope.json")
    assert log.records == {}
    assert log.summary() == {"total": 0, "sent": 0, "dry_run": 0}


def test_record_roundtrips_through_disk(tmp_path):
    path = tmp_path / "sent.json"
    log = SentLog.load(path)
    log.record("SomeHandle", "🎉", "emoji", dry_run=False)
    log.save()

    reloaded = SentLog.load(path)
    assert "somehandle" in reloaded.records
    assert reloaded.summary() == {"total": 1, "sent": 1, "dry_run": 0}


def test_cooldown_blocks_a_recent_send(tmp_path):
    log = SentLog.load(tmp_path / "sent.json")
    log.record("friend", "🎉", "emoji", dry_run=False)
    assert log.in_cooldown("friend", 30) is True
    assert log.in_cooldown("FRIEND", 30) is True
    assert log.in_cooldown("stranger", 30) is False


def test_cooldown_expires(tmp_path):
    log = SentLog.load(tmp_path / "sent.json")
    long_ago = datetime.now(timezone.utc) - timedelta(days=40)
    log.records["friend"] = {"handle": "friend", "sent_at": long_ago.isoformat(), "dry_run": False}
    assert log.in_cooldown("friend", 30) is False


def test_corrupt_log_does_not_crash(tmp_path):
    path = tmp_path / "sent.json"
    path.write_text("{not json", encoding="utf-8")
    assert SentLog.load(path).records == {}
