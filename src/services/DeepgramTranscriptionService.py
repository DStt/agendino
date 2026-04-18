import logging
from pathlib import Path

from deepgram import DeepgramClient, ListenV1Response
from models.dto.CostMetadata import CostMetadata

logger = logging.getLogger(__name__)

# Deepgram Nova pay-as-you-go rate per minute
DEFAULT_RATE_PER_MINUTE = 0.0043


class DeepgramTranscriptionService:
    def __init__(self, api_key: str, rate_per_minute: float = DEFAULT_RATE_PER_MINUTE):
        self._client = DeepgramClient(api_key=api_key)
        self._rate_per_minute = rate_per_minute

    def transcribe(self, audio_path: str, mime_type: str = "audio/mpeg") -> tuple[str, CostMetadata]:
        """Transcribe audio with Deepgram Nova. Returns (transcript, cost_metadata)."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info("Transcribing '%s' with Deepgram Nova...", path.name)

        with open(path, "rb") as f:
            buffer_data = f.read()

        response: ListenV1Response = self._client.listen.v1.media.transcribe_file(
            request=buffer_data,
            model="nova-3",
            smart_format=True,
            diarize=True,
            language="multi",
            punctuate=True,
            utterances=True,
        )

        # Extract duration from metadata
        duration_seconds = response.metadata.duration if response.metadata else 0
        audio_minutes = duration_seconds / 60.0

        # Format transcript from utterances (includes speaker labels + timestamps)
        transcript = self._format_utterances(response.results)

        cost = CostMetadata(
            operation="transcription",
            engine="deepgram",
            model="nova-3",
            input_units=audio_minutes,
            output_units=0,
            cost_usd=round(audio_minutes * self._rate_per_minute, 6),
        )

        logger.info(
            "Deepgram transcription complete: %.1f minutes, $%.4f",
            audio_minutes, cost.cost_usd,
        )
        return transcript, cost

    @staticmethod
    def _format_utterances(results) -> str:
        """Format Deepgram response into [MM:SS] Speaker N: text lines."""
        lines = []

        # Use utterances if available (grouped by speaker turn)
        if results.utterances:
            for utt in results.utterances:
                ts = DeepgramTranscriptionService._format_timestamp(utt.start)
                speaker = utt.speaker + 1  # Deepgram is 0-indexed
                text = utt.transcript.strip()
                if text:
                    lines.append(f"[{ts}] Speaker {speaker}: {text}")
        else:
            # Fallback: use channels/alternatives
            for channel in results.channels:
                for alt in channel.alternatives:
                    if alt.transcript.strip():
                        lines.append(alt.transcript.strip())

        return "\n".join(lines)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"
