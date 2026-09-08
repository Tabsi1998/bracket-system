"""Loads the stored AMP access data for the sync run.

Kept apart from the routes so the scheduler can reach it without importing an
HTTP module, and so the decryption lives in exactly one place.
"""
from __future__ import annotations

from database import get_db
from services.secret_store import decrypt_secret, secret_is_configured


async def load_amp_settings() -> dict | None:
    """Return usable AMP access data, or None if it is not fully configured.

    Half-configured is treated as not configured: without all three values a
    sync attempt would fail anyway, and a clear "not set up" beats a login
    error in the operator's log.
    """
    settings = await get_db().settings.find_one({"id": "amp"}, {"_id": 0}) or {}
    if settings.get("enabled") is False:
        return None
    base_url = str(settings.get("base_url") or "").strip()
    username = str(settings.get("username") or "").strip()
    if not base_url or not username or not secret_is_configured(settings.get("password")):
        return None
    return {
        "base_url": base_url,
        "username": username,
        "password": decrypt_secret(settings.get("password")),
    }
