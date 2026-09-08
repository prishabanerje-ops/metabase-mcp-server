import pytest

from metabase_client import MetabaseConfig, MetabaseError


def test_config_requires_metabase_url(monkeypatch):
    monkeypatch.delenv("METABASE_URL", raising=False)
    with pytest.raises(MetabaseError, match="METABASE_URL"):
        MetabaseConfig()


def test_config_requires_some_auth_method(monkeypatch):
    monkeypatch.setenv("METABASE_URL", "https://metabase.example.com")
    monkeypatch.delenv("METABASE_API_KEY", raising=False)
    monkeypatch.delenv("METABASE_EMAIL", raising=False)
    monkeypatch.delenv("METABASE_PASSWORD", raising=False)
    with pytest.raises(MetabaseError, match="auth"):
        MetabaseConfig()


def test_config_resolves_api_key_mode(monkeypatch):
    monkeypatch.setenv("METABASE_URL", "https://metabase.example.com")
    monkeypatch.setenv("METABASE_API_KEY", "test-key")
    monkeypatch.delenv("METABASE_EMAIL", raising=False)
    monkeypatch.delenv("METABASE_PASSWORD", raising=False)

    config = MetabaseConfig()

    assert config.uses_api_key is True
    assert config.url == "https://metabase.example.com"


def test_config_resolves_session_mode_and_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("METABASE_URL", "https://metabase.example.com/")
    monkeypatch.delenv("METABASE_API_KEY", raising=False)
    monkeypatch.setenv("METABASE_EMAIL", "a@b.com")
    monkeypatch.setenv("METABASE_PASSWORD", "secret")

    config = MetabaseConfig()

    assert config.uses_api_key is False
    assert config.url == "https://metabase.example.com"
