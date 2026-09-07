import pytest
from cryptography.fernet import Fernet

from services.secret_store import (
    PREFIX,
    decrypt_secret,
    encrypt_secret,
    reset_secret_store_cache,
)
from services.totp import current_totp, generate_recovery_codes, provisioning_uri, verify_totp


RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


def test_totp_matches_rfc_sha1_vector_truncated_to_six_digits():
    assert current_totp(RFC_SECRET, at_time=59) == "287082"
    assert verify_totp(RFC_SECRET, "287082", at_time=59)
    assert not verify_totp(RFC_SECRET, "287083", at_time=59, window=0)
    assert not verify_totp(RFC_SECRET, "not-a-code", at_time=59)


def test_totp_uri_and_recovery_codes_are_safe_and_unique():
    uri = provisioning_uri(RFC_SECRET, "admin+test@example.at", "Lion Squad")
    assert uri.startswith("otpauth://totp/")
    assert "admin%2Btest%40example.at" in uri
    codes = generate_recovery_codes(20)
    assert len(codes) == len(set(codes)) == 20
    assert all(len(code) == 10 and code.isalnum() for code in codes)


def test_secret_store_encrypts_and_is_idempotent(monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", key)
    reset_secret_store_cache()
    encrypted = encrypt_secret("super-secret")
    assert encrypted.startswith(PREFIX)
    assert encrypted != "super-secret"
    assert encrypt_secret(encrypted) == encrypted
    assert decrypt_secret(encrypted) == "super-secret"
    reset_secret_store_cache()


def test_secret_store_fails_closed_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SETTINGS_ENCRYPTION_KEY", raising=False)
    reset_secret_store_cache()
    with pytest.raises(RuntimeError, match="required in production"):
        encrypt_secret("secret")
    reset_secret_store_cache()
