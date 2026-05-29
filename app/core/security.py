"""API security helpers."""

from fastapi import Header, HTTPException, status

from app.core.config import Settings, get_settings


def admin_auth_required(settings: Settings | None = None) -> bool:
    """True when mutating endpoints must verify X-Admin-Token."""
    s = settings or get_settings()
    if s.api_admin_token:
        return True
    return s.app_env.lower() in ("production", "staging")


async def verify_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not admin_auth_required(settings):
        return
    if not settings.api_admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_ADMIN_TOKEN is required in production. Set it in environment variables.",
        )
    if x_admin_token != settings.api_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )
