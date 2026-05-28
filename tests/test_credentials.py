from app.core.config import Settings
from app.core.credentials import decrypt_secret, encrypt_secret


def test_encrypt_roundtrip():
    s = Settings(credentials_encryption_key="test-passphrase-for-fernet-key-32b!")
    plain = "sk-secret"
    enc = encrypt_secret(s, plain)
    assert enc != plain
    assert decrypt_secret(s, enc) == plain
