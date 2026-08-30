import base64
import json

import pytest

from tiktok_bot.config import Settings
from tiktok_bot.session import (
    SessionError,
    describe_session,
    encode_for_secret,
    load_storage_state,
    write_storage_state,
)

STATE = {"cookies": [{"name": "sessionid", "value": "x", "domain": ".tiktok.com"}], "origins": []}


def test_describe_reports_flags_not_values():
    described = describe_session(STATE)
    assert described == {"cookie_count": 1, "origins": 0, "has_auth_cookie": True}
    assert "x" not in json.dumps(described)


def test_file_beats_env_blob(tmp_path):
    path = write_storage_state(STATE, tmp_path / "storage_state.json")
    settings = Settings(session_file=path, session_b64=base64.b64encode(b"{}").decode())
    assert load_storage_state(settings) == STATE


def test_env_blob_used_when_no_file(tmp_path):
    blob = base64.b64encode(json.dumps(STATE).encode()).decode()
    settings = Settings(session_file=tmp_path / "absent.json", session_b64=blob)
    assert load_storage_state(settings) == STATE


def test_missing_session_is_an_error(tmp_path):
    with pytest.raises(SessionError):
        load_storage_state(Settings(session_file=tmp_path / "absent.json", session_b64=""))


def test_bad_base64_is_an_error(tmp_path):
    settings = Settings(session_file=tmp_path / "absent.json", session_b64="not base64!!")
    with pytest.raises(SessionError):
        load_storage_state(settings)


def test_non_storage_state_json_rejected(tmp_path):
    path = tmp_path / "storage_state.json"
    path.write_text('{"hello": "world"}', encoding="utf-8")
    with pytest.raises(SessionError):
        load_storage_state(Settings(session_file=path))


def test_encode_roundtrip(tmp_path):
    path = write_storage_state(STATE, tmp_path / "storage_state.json")
    decoded = json.loads(base64.b64decode(encode_for_secret(path)))
    assert decoded == STATE
