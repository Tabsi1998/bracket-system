import pytest

from services import google_identity
from services.google_identity import GoogleIdentityError


def test_google_credential_uses_configured_audience_and_normalizes(monkeypatch):
    seen = {}

    def fake_verify(token, _request, audience):
        seen.update(token=token, audience=audience)
        return {
            "sub": "google-sub-123",
            "email": "Player@Gmail.com",
            "email_verified": True,
            "name": "Lion Player",
            "picture": "https://example.test/avatar.png",
        }

    monkeypatch.setattr(google_identity.id_token, "verify_oauth2_token", fake_verify)
    result = google_identity.verify_google_credential("signed-token", "client.apps.googleusercontent.com")

    assert seen == {"token": "signed-token", "audience": "client.apps.googleusercontent.com"}
    assert result["id"] == "google-sub-123"
    assert result["email"] == "player@gmail.com"
    assert google_identity.google_is_authoritative_for_email(result)


@pytest.mark.parametrize("payload", [
    {"sub": "", "email": "player@gmail.com", "email_verified": True},
    {"sub": "123", "email": "", "email_verified": True},
    {"sub": "123", "email": "player@gmail.com", "email_verified": False},
])
def test_google_credential_rejects_incomplete_identity(monkeypatch, payload):
    monkeypatch.setattr(google_identity.id_token, "verify_oauth2_token", lambda *_args: payload)
    with pytest.raises(GoogleIdentityError):
        google_identity.verify_google_credential("signed-token", "client.apps.googleusercontent.com")


def test_google_credential_rejects_invalid_signature(monkeypatch):
    def fail(*_args):
        raise ValueError("invalid signature")

    monkeypatch.setattr(google_identity.id_token, "verify_oauth2_token", fail)
    with pytest.raises(GoogleIdentityError):
        google_identity.verify_google_credential("forged", "client.apps.googleusercontent.com")
