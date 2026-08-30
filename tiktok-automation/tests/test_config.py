import pytest

from tiktok_bot.config import ConfigError, Selectors, Settings, load_skip_list


def test_sending_needs_both_switches():
    assert Settings(allow_send=True, dry_run=False).sending_enabled is True
    assert Settings(allow_send=True, dry_run=True).sending_enabled is False
    assert Settings(allow_send=False, dry_run=False).sending_enabled is False
    assert Settings().sending_enabled is False


def test_defaults_are_safe():
    settings = Settings()
    assert settings.dry_run is True
    assert settings.allow_send is False


def test_from_env_strips_at_sign(monkeypatch):
    monkeypatch.setenv("TIKTOK_USERNAME", "@someone")
    assert Settings.from_env().username == "someone"


def test_invalid_mode_rejected():
    with pytest.raises(ConfigError):
        Settings(message_mode="carrier-pigeon").validate()


def test_inverted_delays_rejected():
    with pytest.raises(ConfigError):
        Settings(min_delay_seconds=90, max_delay_seconds=10).validate()


def test_selectors_normalise_to_lists(tmp_path):
    path = tmp_path / "selectors.yml"
    path.write_text("a:\n  single: '.one'\n  many: ['.x', '.y']\n", encoding="utf-8")
    selectors = Selectors.load(path)
    assert selectors.get("a.single") == [".one"]
    assert selectors.get("a.many") == [".x", ".y"]
    with pytest.raises(ConfigError):
        selectors.get("a.missing")


def test_skip_list_ignores_comments_and_at_signs(tmp_path):
    path = tmp_path / "skip.txt"
    path.write_text("# a note\n@Alice\nbob  # trailing\n\n", encoding="utf-8")
    assert load_skip_list(path) == {"alice", "bob"}
    assert load_skip_list(tmp_path / "absent.txt") == set()
