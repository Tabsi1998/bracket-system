"""Verification helpers for Google Identity Services ID tokens.

The browser only obtains the credential. Trust is established here by the
official google-auth library using Google's rotating public signing keys.
"""
from __future__ import annotations

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


class GoogleIdentityError(ValueError):
    """Raised when a Google credential cannot be trusted or is incomplete."""


def verify_google_credential(credential: str, client_id: str) -> dict:
    token = (credential or "").strip()
    audience = (client_id or "").strip()
    if not token:
        raise GoogleIdentityError("Google-Credential fehlt")
    if not audience:
        raise GoogleIdentityError("Google-Login ist nicht konfiguriert")

    try:
        payload = id_token.verify_oauth2_token(token, google_requests.Request(), audience)
    except (ValueError, GoogleAuthError, OSError) as exc:
        raise GoogleIdentityError("Google-Credential ist ungültig oder abgelaufen") from exc

    subject = str(payload.get("sub") or "").strip()
    email = str(payload.get("email") or "").lower().strip()
    if not subject or not email or payload.get("email_verified") is not True:
        raise GoogleIdentityError("Google-Konto besitzt keine bestätigte E-Mail-Adresse")

    return {
        "id": subject,
        "email": email,
        "email_verified": True,
        "name": str(payload.get("name") or "").strip(),
        "picture": str(payload.get("picture") or "").strip() or None,
        "hosted_domain": str(payload.get("hd") or "").lower().strip() or None,
    }


def google_is_authoritative_for_email(identity: dict) -> bool:
    """Google is authoritative for Gmail and verified Workspace identities."""
    email = str(identity.get("email") or "").lower()
    return email.endswith("@gmail.com") or bool(identity.get("hosted_domain"))
