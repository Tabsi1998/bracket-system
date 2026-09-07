"""Application-layer encryption for credentials stored in MongoDB."""
from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

PREFIX = "enc:v1:"


def _environment() -> str:
    return os.environ.get("APP_ENV", "development").strip().lower()


@lru_cache(maxsize=1)
def _cipher() -> Fernet:
    configured = os.environ.get("SETTINGS_ENCRYPTION_KEY", "").strip()
    if configured:
        try:
            return Fernet(configured.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("SETTINGS_ENCRYPTION_KEY must be a valid Fernet key.") from exc
    if _environment() in {"production", "prod"}:
        raise RuntimeError("SETTINGS_ENCRYPTION_KEY is required in production.")
    seed = os.environ.get("JWT_SECRET", "tls-local-development-secret-store")
    derived = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
    return Fernet(derived)


def encrypt_secret(value: object) -> str:
    plaintext = str(value or "")
    if not plaintext or plaintext.startswith(PREFIX):
        return plaintext
    return PREFIX + _cipher().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(value: object) -> str:
    stored = str(value or "")
    if not stored or not stored.startswith(PREFIX):
        return stored
    try:
        return _cipher().decrypt(stored[len(PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise RuntimeError("A stored secret cannot be decrypted with SETTINGS_ENCRYPTION_KEY.") from exc


def secret_is_configured(value: object) -> bool:
    return bool(str(value or "").strip())


def reset_secret_store_cache() -> None:
    """Test helper for environment changes."""
    _cipher.cache_clear()
