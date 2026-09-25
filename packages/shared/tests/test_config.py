import pytest

from shared.config import Settings


def test_defaults_load_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None)
    assert settings.telephony_provider == "plivo"
    assert settings.max_call_duration_s == 360


def test_env_overrides_and_secrets_are_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/1")
    monkeypatch.setenv("SARVAM_API_KEY", "sk-test-123")
    settings = Settings(_env_file=None)
    assert settings.redis_url == "redis://redis:6379/1"
    assert settings.sarvam_api_key is not None
    assert settings.sarvam_api_key.get_secret_value() == "sk-test-123"
    assert "sk-test-123" not in repr(settings)
