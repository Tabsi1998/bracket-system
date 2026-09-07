"""Centralized authentication/login configuration, editable from the admin area.

Stored as a single settings document (id="auth"). Federated login defaults to
off until an administrator has supplied a client owned by the club.
"""
from __future__ import annotations

from database import get_db

AUTH_SETTINGS_DEFAULTS = {
    "password_login_enabled": True,
    "registration_enabled": True,
    "google_login_enabled": False,
    "google_registration_enabled": False,
    "google_linking_enabled": False,
    "google_client_id": "",
}

AUTH_SETTINGS_KEYS = tuple(AUTH_SETTINGS_DEFAULTS.keys())


def is_google_client_id(value: object) -> bool:
    client_id = str(value or "").strip()
    return bool(client_id and client_id.endswith(".apps.googleusercontent.com") and len(client_id) <= 255)


async def load_auth_settings(db=None) -> dict:
    if db is None:
        db = get_db()
    doc = await db.settings.find_one({"id": "auth"}, {"_id": 0}) or {}
    result = dict(AUTH_SETTINGS_DEFAULTS)
    for key in AUTH_SETTINGS_KEYS:
        default = AUTH_SETTINGS_DEFAULTS[key]
        value = doc.get(key)
        if isinstance(default, bool) and isinstance(value, bool):
            result[key] = value
        elif isinstance(default, str) and isinstance(value, str):
            result[key] = value.strip()
    configured = is_google_client_id(result["google_client_id"])
    result["google_configured"] = configured
    if not configured:
        result["google_login_enabled"] = False
        result["google_registration_enabled"] = False
        result["google_linking_enabled"] = False
    return result
