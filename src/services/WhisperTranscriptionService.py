import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class WhisperTranscriptionService:
    """Transcribe audio locally using faster-whisper (CTranslate2 Whisper)."""

    def __init__(self, model_size: str, device: str, compute_type: str):
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = None  # lazy-loaded

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading Whisper model '%s' (device=%s, compute_type=%s)…",
                self._model_size,
                self._device,
                self._compute_type,
            )
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info("Whisper model loaded.")
        return self._model

    def transcribe(self, audio_path: str, mime_type: str = "audio/mpeg") -> str:
        """Transcribe an audio file locally with Whisper and return formatted text."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info("Transcribing '%s' with local Whisper (%s)…", path.name, self._model_size)

        model = self._get_model()
        segments, info = model.transcribe(
            str(path),
            beam_size=5,
            vad_filter=True,
        )

        logger.info(
            "Detected language: %s (probability %.2f)",
            info.language,
            info.language_probability,
        )

        lines = []
        for segment in segments:
            ts = self._format_timestamp(segment.start)
            text = segment.text.strip()
            if text:
                lines.append(f"[{ts}] {text}")

        transcript = "\n".join(lines)
        logger.info("Whisper transcription complete (%d segments).", len(lines))
        return transcript

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Convert seconds to MM:SS format."""
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"
