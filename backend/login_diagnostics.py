"""Read-only, shareable login/mail status. Never sends mail or changes accounts.

Run from checkout on the Docker host (no rebuild required):
docker compose exec -T backend python - person@example.test < backend/login_diagnostics.py
"""
import argparse
import asyncio
import json
import os
from datetime import datetime, timezone

from database import get_db
from services.mail_queue import get_mail_settings


def error_category(value):
    """Classify locally; never output raw provider errors (may contain secrets)."""
    text = str(value or "").lower()
    if not text:
        return None
    for category, needles in (
        ("disabled", ("deaktiviert", "disabled")),
        ("missing_configuration", ("not configured", "no api key", "credentials")),
        ("authentication", ("authentication", "authenticate", "535", "api key", "unauthorized")),
        ("relay_denied", ("relay",)),
        ("tls_certificate", ("certificate", "zertifikat")),
        ("network", ("timeout", "timed out", "connection", "connect", "name resolution")),
        ("sender_or_recipient", ("sender", "recipient", "550", "domain")),
    ):
        if any(needle in text for needle in needles):
            return category
    return "other_delivery_error"


async def report(email):
    db = get_db()
    user = await db.users.find_one({"email": email.strip().lower()}, {
        "_id": 0, "id": 1, "email_verified": 1, "is_active": 1,
        "is_banned": 1, "mfa_enabled": 1, "password_setup_required": 1,
    })
    result = {
        "schema": "tls.login-diagnostics.v1", "read_only": True,
        "account_found": bool(user),
        "scheduler_disabled": os.environ.get("DISABLE_SCHEDULER", "").lower() == "true",
        "frontend_url_configured": bool(os.environ.get("FRONTEND_URL", "").strip()),
    }
    if user:
        result["account"] = {key: user.get(key) for key in (
            "email_verified", "is_active", "is_banned", "mfa_enabled", "password_setup_required",
        )}
        result["active_verification_links"] = await db.email_verification_tokens.count_documents({
            "user_id": user["id"], "used": False,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        })
    try:
        cfg = await get_mail_settings()
        result["mail"] = {
            "enabled": bool(cfg["enabled"]),
            "provider": cfg["provider"] if cfg["provider"] in {"smtp", "resend"} else "unknown",
            "smtp_host_configured": bool(cfg.get("smtp_host")),
            "smtp_user_configured": bool(cfg.get("smtp_user")),
            "smtp_password_configured": bool(cfg.get("smtp_pass")),
            "resend_key_configured": bool(cfg.get("resend_api_key")),
        }
    except Exception:
        result["mail"] = {"configuration_readable": False,
                          "hint": "Check settings encryption key and mail configuration locally; do not share secrets."}
    jobs = await db.mail_jobs.find({
        "to": email.strip().lower(), "template_key": {"$in": ["email_verification", "password_reset"]},
    }, {"_id": 0, "status": 1, "template_key": 1, "attempts": 1,
        "created_at": 1, "next_attempt_at": 1, "last_error": 1}).sort("created_at", -1).limit(5).to_list(5)
    result["recent_auth_mail"] = [{
        "status": job.get("status"), "template": job.get("template_key"),
        "attempts": job.get("attempts"), "created_at": job.get("created_at"),
        "next_attempt_at": job.get("next_attempt_at"),
        "error_category": error_category(job.get("last_error")),
    } for job in jobs]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Account email; output omits the address and all secrets")
    args = parser.parse_args()
    try:
        result = asyncio.run(asyncio.wait_for(report(args.email), timeout=20))
    except Exception:
        print(json.dumps({"read_only": True, "error": "diagnostic_unavailable",
                          "hint": "Run inside the backend container with database access."}))
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
