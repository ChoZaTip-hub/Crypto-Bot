"""Settings must read OPENAI_API_KEY from .env (not only AI_API_KEY)."""

import os

from app.core.config import Settings, get_settings


def test_openai_api_key_env_alias(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.setenv("AI_ENABLED", "true")
    s = Settings(_env_file=None)
    assert s.ai_api_key == "sk-test-openai"
    assert s.ai_enabled is True


def test_ai_api_key_env_alias(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "sk-test-ai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.ai_api_key == "sk-test-ai"


def test_get_settings_reads_openai_from_dotenv(monkeypatch):
    """Regression: .env uses OPENAI_API_KEY= without exporting to os.environ."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    get_settings.cache_clear()
    s = get_settings()
    if not s.ai_enabled:
        return
    assert s.ai_api_key.strip(), "OPENAI_API_KEY in .env should populate ai_api_key"
