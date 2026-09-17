import os
from unittest.mock import MagicMock

import pytest

# Must be set before importing the app so load_dotenv does not re-enable auth.
os.environ["AUTH_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app import depends  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client_and_mock():
    mock = MagicMock()
    mock.get_audio_file_path.return_value = (None, "")
    app.dependency_overrides[depends.get_dashboard_controller] = lambda: mock
    yield TestClient(app), mock
    app.dependency_overrides.clear()


class TestRecordingNameValidation:
    def test_backslash_name_is_rejected(self, client_and_mock):
        client, mock = client_and_mock
        resp = client.get("/api/dashboard/audio/a%5Cb.mp3")
        assert resp.status_code == 422
        mock.get_audio_file_path.assert_not_called()

    def test_valid_name_reaches_controller(self, client_and_mock):
        client, mock = client_and_mock
        client.get("/api/dashboard/audio/meeting-2024.mp3")
        mock.get_audio_file_path.assert_called_once()


class TestSanitizerAssets:
    def test_home_page_loads_sanitizer(self):
        resp = TestClient(app).get("/")
        assert resp.status_code == 200
        assert "/static/vendor/purify.min.js" in resp.text
        assert "/static/sanitize.js" in resp.text

    def test_sanitizer_script_is_served(self):
        resp = TestClient(app).get("/static/sanitize.js")
        assert resp.status_code == 200
        assert "sanitizeHtml" in resp.text
