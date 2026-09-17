import pytest

from services.TranscriptionService import TranscriptionService


class TestTranscriptionServiceOptionalClient:
    def test_missing_key_does_not_raise(self):
        service = TranscriptionService(api_key=None)
        assert service.is_configured is False

    def test_empty_key_does_not_raise(self):
        service = TranscriptionService(api_key="")
        assert service.is_configured is False

    def test_transcribe_without_key_raises_value_error(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"x")
        service = TranscriptionService(api_key=None)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            service.transcribe(str(audio))

    def test_injected_model_is_used(self):
        service = TranscriptionService(api_key=None, model="gemini-x")
        assert service._model == "gemini-x"

    def test_default_model_is_applied(self):
        service = TranscriptionService(api_key=None)
        assert service._model

    def test_configured_with_key(self):
        service = TranscriptionService(api_key="fake-key")
        assert service.is_configured is True
