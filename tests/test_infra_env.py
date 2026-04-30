"""env loader: os.environ wins over .env file wins over default."""

from __future__ import annotations


def test_env_falls_back_to_default(clean_env, monkeypatch):
    from ap_org_bot.infra import env as env_mod
    # Force file-env to be empty too.
    monkeypatch.setattr(env_mod, "_FILE_ENV", {})
    assert env_mod.env("UNDEFINED_KEY", "default-value") == "default-value"


def test_env_reads_file_when_no_os(clean_env, monkeypatch):
    from ap_org_bot.infra import env as env_mod
    monkeypatch.setattr(env_mod, "_FILE_ENV", {"FOO_KEY": "from-file"})
    assert env_mod.env("FOO_KEY", "default") == "from-file"


def test_env_os_wins_over_file(clean_env, monkeypatch):
    from ap_org_bot.infra import env as env_mod
    monkeypatch.setattr(env_mod, "_FILE_ENV", {"FOO_KEY": "from-file"})
    monkeypatch.setenv("FOO_KEY", "from-os")
    assert env_mod.env("FOO_KEY", "default") == "from-os"


def test_env_int_parses_or_falls_back(clean_env, monkeypatch):
    from ap_org_bot.infra import env as env_mod
    monkeypatch.setattr(env_mod, "_FILE_ENV", {"OK": "42", "BAD": "xyz"})
    assert env_mod.env_int("OK", 0) == 42
    assert env_mod.env_int("BAD", 7) == 7
    assert env_mod.env_int("MISSING", 9) == 9


def test_env_bool_recognizes_common_truth_strings(clean_env, monkeypatch):
    from ap_org_bot.infra import env as env_mod
    truthy = ["1", "true", "TRUE", "yes", "on"]
    falsy = ["0", "false", "no", "off"]
    for v in truthy:
        monkeypatch.setattr(env_mod, "_FILE_ENV", {"K": v})
        assert env_mod.env_bool("K", False) is True
    for v in falsy:
        monkeypatch.setattr(env_mod, "_FILE_ENV", {"K": v})
        assert env_mod.env_bool("K", True) is False


def test_env_bool_default_when_unparsable(clean_env, monkeypatch):
    from ap_org_bot.infra import env as env_mod
    monkeypatch.setattr(env_mod, "_FILE_ENV", {"K": "maybe"})
    assert env_mod.env_bool("K", True) is True
    assert env_mod.env_bool("K", False) is False
