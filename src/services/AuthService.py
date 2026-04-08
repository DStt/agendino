import hashlib
import json
import logging
import os
import secrets
import time

logger = logging.getLogger(__name__)

SESSION_DURATION = 60 * 60 * 24 * 7


class AuthService:
    """Single-user authentication with file-based session storage."""

    def __init__(self, settings_path: str):
        self.credentials_file = os.path.join(settings_path, "auth.json")
        self.sessions_file = os.path.join(settings_path, "sessions.json")

    # ── Password hashing ──────────────────────────────────────────

    @staticmethod
    def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        actual_salt: str = salt if salt is not None else secrets.token_hex(32)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), actual_salt.encode(), 200_000).hex()
        return hashed, actual_salt

    # ── Credentials persistence ───────────────────────────────────

    def _load_credentials(self) -> dict | None:
        if not os.path.exists(self.credentials_file):
            return None
        with open(self.credentials_file, "r") as f:
            return json.load(f)

    def _save_credentials(self, username: str, password: str) -> None:
        hashed, salt = self._hash_password(password)
        data = {"username": username, "password_hash": hashed, "salt": salt}
        with open(self.credentials_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("First-login credentials saved for user '%s'", username)

    def has_credentials(self) -> bool:
        return os.path.exists(self.credentials_file)

    # ── Authentication ────────────────────────────────────────────

    def authenticate(self, username: str, password: str) -> bool:
        creds = self._load_credentials()

        if creds is None:
            # First login ever → persist credentials
            self._save_credentials(username, password)
            return True

        if username != creds["username"]:
            return False

        hashed, _ = self._hash_password(password, creds["salt"])
        return secrets.compare_digest(hashed, creds["password_hash"])

    # ── Session management (JSON file) ────────────────────────────

    def _load_sessions(self) -> dict:
        if not os.path.exists(self.sessions_file):
            return {}
        try:
            with open(self.sessions_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_sessions(self, sessions: dict) -> None:
        with open(self.sessions_file, "w") as f:
            json.dump(sessions, f, indent=2)

    def create_session(self) -> str:
        token = secrets.token_hex(32)
        sessions = self._load_sessions()
        # Purge expired sessions
        now = time.time()
        sessions = {k: v for k, v in sessions.items() if v > now}
        sessions[token] = now + SESSION_DURATION
        self._save_sessions(sessions)
        return token

    def validate_session(self, token: str) -> bool:
        if not token:
            return False
        sessions = self._load_sessions()
        expiry = sessions.get(token)
        if expiry is None:
            return False
        if time.time() > float(expiry):
            del sessions[token]
            self._save_sessions(sessions)
            return False
        return True

    def destroy_session(self, token: str) -> None:
        sessions = self._load_sessions()
        if token in sessions:
            del sessions[token]
            self._save_sessions(sessions)
