import json
import os
import tempfile
import time

import pytest

from services.AuthService import AuthService


@pytest.fixture
def auth_dir(tmp_path):
    """Return a temporary directory for auth files."""
    return str(tmp_path)


@pytest.fixture
def auth_service(auth_dir):
    return AuthService(settings_path=auth_dir)


class TestFirstLogin:
    def test_first_login_creates_credentials(self, auth_service, auth_dir):
        assert not auth_service.has_credentials()
        assert auth_service.authenticate("admin", "secret123")
        assert auth_service.has_credentials()

        with open(os.path.join(auth_dir, "auth.json")) as f:
            creds = json.load(f)
        assert creds["username"] == "admin"
        assert "password_hash" in creds
        assert "salt" in creds
        # password is NOT stored in plain text
        assert creds["password_hash"] != "secret123"

    def test_first_login_any_credentials_accepted(self, auth_service):
        assert auth_service.authenticate("foo", "bar")


class TestSubsequentLogin:
    def test_correct_credentials(self, auth_service):
        auth_service.authenticate("admin", "secret123")  # first login
        assert auth_service.authenticate("admin", "secret123")

    def test_wrong_password(self, auth_service):
        auth_service.authenticate("admin", "secret123")
        assert not auth_service.authenticate("admin", "wrong")

    def test_wrong_username(self, auth_service):
        auth_service.authenticate("admin", "secret123")
        assert not auth_service.authenticate("other", "secret123")


class TestSessions:
    def test_create_and_validate_session(self, auth_service):
        token = auth_service.create_session()
        assert isinstance(token, str)
        assert len(token) == 64  # 32 bytes hex
        assert auth_service.validate_session(token)

    def test_invalid_token_rejected(self, auth_service):
        assert not auth_service.validate_session("")
        assert not auth_service.validate_session("nonexistent")

    def test_destroy_session(self, auth_service):
        token = auth_service.create_session()
        assert auth_service.validate_session(token)
        auth_service.destroy_session(token)
        assert not auth_service.validate_session(token)

    def test_expired_session_rejected(self, auth_dir):
        service = AuthService(settings_path=auth_dir)
        token = "expired-token"
        sessions = {token: time.time() - 1}  # already expired
        with open(os.path.join(auth_dir, "sessions.json"), "w") as f:
            json.dump(sessions, f)
        assert not service.validate_session(token)

    def test_multiple_sessions(self, auth_service):
        t1 = auth_service.create_session()
        t2 = auth_service.create_session()
        assert auth_service.validate_session(t1)
        assert auth_service.validate_session(t2)
        auth_service.destroy_session(t1)
        assert not auth_service.validate_session(t1)
        assert auth_service.validate_session(t2)

    def test_expired_sessions_purged_on_create(self, auth_dir):
        service = AuthService(settings_path=auth_dir)
        # Manually write an expired session
        sessions = {"old-token": time.time() - 100}
        with open(os.path.join(auth_dir, "sessions.json"), "w") as f:
            json.dump(sessions, f)

        service.create_session()

        with open(os.path.join(auth_dir, "sessions.json")) as f:
            data = json.load(f)
        assert "old-token" not in data

