"""API security helpers."""

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_admin_token:
        return
    if x_admin_token != settings.api_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )
