import asyncio

from services.auth_settings import is_google_client_id, load_auth_settings


class _SettingsCollection:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, *_args, **_kwargs):
        return self.doc


class _Db:
    def __init__(self, doc=None):
        self.settings = _SettingsCollection(doc or {})


def test_google_features_are_off_without_owned_client():
    settings = asyncio.run(load_auth_settings(_Db({
        "google_login_enabled": True,
        "google_registration_enabled": True,
        "google_linking_enabled": True,
    })))
    assert settings["google_configured"] is False
    assert settings["google_login_enabled"] is False
    assert settings["google_registration_enabled"] is False
    assert settings["google_linking_enabled"] is False


def test_valid_client_allows_explicit_google_flags():
    settings = asyncio.run(load_auth_settings(_Db({
        "google_client_id": "123-example.apps.googleusercontent.com",
        "google_login_enabled": True,
        "google_registration_enabled": False,
        "google_linking_enabled": True,
    })))
    assert settings["google_configured"] is True
    assert settings["google_login_enabled"] is True
    assert settings["google_registration_enabled"] is False
    assert settings["google_linking_enabled"] is True


def test_google_client_id_validation():
    assert is_google_client_id("123-example.apps.googleusercontent.com")
    assert not is_google_client_id("")
    assert not is_google_client_id("secret")
    assert not is_google_client_id("https://accounts.google.com")
