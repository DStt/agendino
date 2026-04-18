import os
import logging
from pathlib import Path
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

TRANSCRIPTION_PROMPT = """\
Transcribe the following audio recording accurately and completely.
Use the language spoken in the audio - do NOT translate.

Rules:
- Identify distinct speakers and label them as Speaker 1, Speaker 2, etc.
- If a speaker's name is mentioned at any point, replace their generic
  label with that name throughout the entire transcript.
- Include a timestamp at the start of each new speaker turn in [MM:SS] format.
- Remove filler sounds and hesitation noises (e.g. Mm, Mhm, Uh, Eh, Ah, Um)
  unless they carry clear communicative intent.
- Mark unclear or inaudible speech as [inaudible].
- Use proper punctuation and paragraph breaks for readability.
- Do not paraphrase, summarize, or omit content.

Output format:
[00:00] Speaker 1: ...
[00:15] Speaker 2: ...
"""

MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")


class TranscriptionService:
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def transcribe(self, audio_path: str, mime_type: str = "audio/mpeg") -> str:
        """Upload an audio file to Gemini and return the transcription text."""

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info("Uploading '%s' to Gemini…", path.name)
        uploaded = self._client.files.upload(
            file=path,
            config=types.UploadFileConfig(mime_type=mime_type),
        )
        logger.info("Uploaded (%s). Transcribing…", uploaded.name)

        response = self._client.models.generate_content(
            model=MODEL,
            contents=[uploaded, TRANSCRIPTION_PROMPT],
        )
        return response.text
