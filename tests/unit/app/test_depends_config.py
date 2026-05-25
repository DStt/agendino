from pathlib import Path

import pytest
from fastapi import HTTPException

from app import depends


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    depends.config.clear()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    yield
    depends.config.clear()


def test_root_path_points_to_project_root():
    root = Path(depends.get_root_path())

    assert root.name == "agendinostegee"
    assert depends.DOTENV_PATH == root / ".env"


def test_get_config_uses_safe_defaults():
    config = depends.get_config()

    assert config["DATABASE_NAME"] == "agendino.db"
    assert config["GEMINI_MODEL"] == "gemini-2.5-flash"
    assert config["GEMINI_EMBEDDING_MODEL"] == "gemini-embedding-001"
    assert config["AUTH_ENABLED"] == "false"


@pytest.mark.parametrize(
    "api_key",
    [
        None,
        "",
        "   ",
        "AIzaS",
        "your-gemini-api-key",
        "your-real-gemini-api-key",
        "AIzaSy...",
        "not-a-google-api-key",
    ],
)
def test_get_gemini_api_key_rejects_missing_placeholder_and_malformed_values(monkeypatch, api_key):
    if api_key is not None:
        monkeypatch.setenv("GEMINI_API_KEY", api_key)

    with pytest.raises(HTTPException) as exc:
        depends.get_gemini_api_key()

    assert exc.value.status_code == 503
    assert "GEMINI_API_KEY is missing or invalid" in exc.value.detail
    assert str(depends.DOTENV_PATH) in exc.value.detail
    if api_key:
        assert api_key not in exc.value.detail


def test_get_gemini_api_key_accepts_well_formed_google_api_key(monkeypatch):
    expected = "AIza" + ("a" * 35)
    monkeypatch.setenv("GEMINI_API_KEY", f"  {expected}  ")

    assert depends.get_gemini_api_key() == expected
