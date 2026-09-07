"""RFC 6238 TOTP helpers without an external authentication service."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

PERIOD_SECONDS = 30
DIGITS = 6


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _counter_code(secret: str, counter: int) -> str:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return f"{value:0{DIGITS}d}"


def current_totp(secret: str, at_time: int | None = None) -> str:
    timestamp = int(time.time() if at_time is None else at_time)
    return _counter_code(secret, timestamp // PERIOD_SECONDS)


def verify_totp(secret: str, code: str, at_time: int | None = None, window: int = 1) -> bool:
    normalized = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(normalized) != DIGITS:
        return False
    timestamp = int(time.time() if at_time is None else at_time)
    counter = timestamp // PERIOD_SECONDS
    return any(hmac.compare_digest(_counter_code(secret, counter + offset), normalized) for offset in range(-window, window + 1))


def provisioning_uri(secret: str, account: str, issuer: str = "THE LION SQUAD") -> str:
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={quote(secret)}&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={PERIOD_SECONDS}"


def generate_recovery_codes(count: int = 10) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ["".join(secrets.choice(alphabet) for _ in range(10)) for _ in range(count)]
