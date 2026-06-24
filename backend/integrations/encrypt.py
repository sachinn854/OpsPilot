"""
Token encryption using Fernet (AES-128-CBC + HMAC-SHA256).

Tokens are encrypted before storing in DB and decrypted on fetch.
ENCRYPTION_KEY must be a URL-safe base64-encoded 32-byte key.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import os

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY", "").strip()
    if not key:
        # Dev fallback — deterministic key derived from a constant.
        # In production, always set ENCRYPTION_KEY in .env.
        key = "ZmFrZWtleWZha2VrZXlmYWtla2V5ZmFrZWtleWZha2U="
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a plaintext token and return a base64-encoded ciphertext string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plaintext. Raises ValueError on failure."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token decryption failed — wrong key or corrupted data.") from exc
