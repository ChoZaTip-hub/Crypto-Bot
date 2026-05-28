"""Encrypt exchange API secrets at rest (Fernet)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import Settings


def _fernet(settings: Settings) -> Fernet | None:
    raw = (settings.credentials_encryption_key or "").strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    except Exception:
        # Derive a valid Fernet key from arbitrary passphrase
        digest = hashlib.sha256(raw.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)


def encrypt_secret(settings: Settings, plaintext: str) -> str:
    if not plaintext:
        return ""
    f = _fernet(settings)
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(settings: Settings, ciphertext: str) -> str:
    if not ciphertext:
        return ""
    f = _fernet(settings)
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext
