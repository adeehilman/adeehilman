from tiktok_bot.config import Settings
from tiktok_bot.runner import select_targets
from tiktok_bot.scraper import Account
from tiktok_bot.state import SentLog


def _settings(tmp_path, **kwargs):
    defaults = dict(max_messages=5, resend_cooldown_days=30, skip_list_file=tmp_path / "skip.txt")
    defaults.update(kwargs)
    return Settings(**defaults)


def _accounts(*handles):
    return [Account(handle=handle) for handle in handles]


def test_skip_list_is_honoured(tmp_path):
    (tmp_path / "skip.txt").write_text("bob\n", encoding="utf-8")
    settings = _settings(tmp_path)
    targets = select_targets(_accounts("alice", "bob", "carol"), settings, SentLog(tmp_path / "s.json"))
    assert [t.handle for t in targets] == ["alice", "carol"]


def test_cooldown_removes_recent_recipients(tmp_path):
    sent_log = SentLog(tmp_path / "s.json")
    sent_log.record("alice", "🎉", "emoji", dry_run=False)
    targets = select_targets(_accounts("alice", "bob"), _settings(tmp_path), sent_log)
    assert [t.handle for t in targets] == ["bob"]


def test_run_budget_truncates(tmp_path):
    settings = _settings(tmp_path, max_messages=2)
    targets = select_targets(_accounts("a", "b", "c", "d"), settings, SentLog(tmp_path / "s.json"))
    assert len(targets) == 2


def test_only_narrows_and_still_filters(tmp_path):
    (tmp_path / "skip.txt").write_text("bob\n", encoding="utf-8")
    targets = select_targets(
        _accounts("alice", "bob", "carol"),
        _settings(tmp_path),
        SentLog(tmp_path / "s.json"),
        only=["@Alice", "bob"],
    )
    assert [t.handle for t in targets] == ["alice"]
