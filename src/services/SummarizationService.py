import os
import json
import logging

from json_repair import repair_json

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
MAX_OUTPUT_TOKENS = 65536

STRUCTURED_INSTRUCTIONS = """

IMPORTANT — In addition to the summary, you MUST also return:
1. A short descriptive **title** for this recording (max 10 words, suitable as a label).
2. A list of **tags** (3-8 keyword tags) to categorize the content of the recording.

You MUST respond with a valid JSON object with exactly these keys:
{
  "title": "Short descriptive title",
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "The full markdown summary as described above"
}

Return ONLY the JSON object, no other text before or after it.
Use the language from the instruction not the transcript to generate the summary, title, and tags.
"""


class SummarizationService:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        from google import genai

        self._client = genai.Client(api_key=key)

    def summarize(self, transcript: str, system_prompt: str, recording_datetime: str | None = None) -> dict:
        """Summarize a transcript and return structured result with title, tags, and summary."""
        from google.genai import types

        # Build the enriched system instruction
        full_system_prompt = system_prompt + STRUCTURED_INSTRUCTIONS

        # Build user content with recording metadata
        user_content = ""
        if recording_datetime:
            user_content += f"Recording date/time: {recording_datetime}\n\n"
        user_content += transcript

        logger.info("Generating structured summary with Gemini…")
        response = self._client.models.generate_content(
            model=MODEL,
            config=types.GenerateContentConfig(
                system_instruction=full_system_prompt,
                response_mime_type="application/json",
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
            contents=user_content,
        )

        # Detect truncation due to token limit
        truncated = False
        try:
            finish_reason = response.candidates[0].finish_reason
            if finish_reason and str(finish_reason).upper() in ("MAX_TOKENS", "2"):
                logger.warning("Gemini response was truncated (finish_reason=%s), will attempt repair", finish_reason)
                truncated = True
        except (IndexError, AttributeError):
            pass

        raw = response.text or ""
        return self._parse_response(raw, truncated=truncated)

    @staticmethod
    def _parse_response(raw: str, truncated: bool = False) -> dict:
        """Parse the JSON response from Gemini into title, tags, summary."""

        def _extract(data: dict) -> dict:
            title = data.get("title", "").strip()
            tags_raw = data.get("tags", [])
            if isinstance(tags_raw, list):
                tags = [str(t).strip() for t in tags_raw if str(t).strip()]
            else:
                tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()]
            summary = data.get("summary", "").strip()
            if truncated and summary:
                summary += "\n\n> ⚠️ *This summary may be incomplete — the AI response was truncated.*"
            return {"title": title, "tags": tags, "summary": summary}

        # 1. Try strict JSON parse first
        try:
            data = json.loads(raw)
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, dict):
                return _extract(data)
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

        # 2. Fallback: repair truncated / malformed JSON
        logger.warning("Strict JSON parse failed, attempting repair…")
        try:
            repaired = repair_json(raw, return_objects=True)
            if isinstance(repaired, str):
                repaired = json.loads(repaired)
            if isinstance(repaired, dict):
                logger.info("JSON repair succeeded")
                return _extract(repaired)
        except Exception as e:
            logger.warning("JSON repair also failed: %s", e)

        # 3. Last resort: return raw text as summary
        logger.warning("All JSON parsing failed, returning raw text as summary")
        return {"title": "", "tags": [], "summary": raw.strip()}
