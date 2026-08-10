"""
Summarization backed by the Claude (Anthropic) API.

Mirrors the public surface of SummarizationService so it can be used
interchangeably wherever a summarization service is injected. Claude is only used
for summarization — its API has no audio input, so transcription stays on
Gemini/Whisper.
"""
import logging

import anthropic

from services.SummarizationService import STRUCTURED_INSTRUCTIONS, SummarizationService

logger = logging.getLogger(__name__)

# Generous ceiling for a structured summary; streamed so we don't hit the SDK's
# non-streaming HTTP-timeout guard on large outputs.
MAX_OUTPUT_TOKENS = 32000

# Structured-output schema enforcing the same shape the Gemini path produces.
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["title", "tags", "summary"],
    "additionalProperties": False,
}


class ClaudeSummarizationService:
    def __init__(self, api_key: str, model: str):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def summarize(self, transcript: str, system_prompt: str, recording_datetime: str | None = None) -> dict:
        """Summarize a transcript and return structured result with title, tags, and summary."""

        # Same enriched system instruction the Gemini service builds.
        full_system_prompt = system_prompt + STRUCTURED_INSTRUCTIONS

        user_content = ""
        if recording_datetime:
            user_content += f"Recording date/time: {recording_datetime}\n\n"
        user_content += transcript

        logger.info("Generating structured summary with Claude…")
        with self._client.messages.stream(
            model=self._model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=full_system_prompt,
            output_config={"format": {"type": "json_schema", "schema": SUMMARY_SCHEMA}},
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            message = stream.get_final_message()

        truncated = message.stop_reason == "max_tokens"
        if truncated:
            logger.warning("Claude response hit max_tokens, will attempt repair")

        raw = next((block.text for block in message.content if block.type == "text"), "")
        # Reuse the Gemini service's parser so title/tags/summary extraction and the
        # json-repair fallback stay identical across providers.
        return SummarizationService._parse_response(raw, truncated=truncated)
