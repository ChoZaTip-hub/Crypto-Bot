"""Security helpers."""

from app.core.config import Settings
from app.core.security import admin_auth_required


def test_admin_auth_required_when_token_set() -> None:
    assert admin_auth_required(Settings(api_admin_token="secret", app_env="development")) is True


def test_admin_auth_required_in_production() -> None:
    assert admin_auth_required(Settings(api_admin_token="", app_env="production")) is True


def test_admin_auth_optional_in_dev() -> None:
    assert admin_auth_required(Settings(api_admin_token="", app_env="development")) is False
