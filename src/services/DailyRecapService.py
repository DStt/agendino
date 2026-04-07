import json
import logging

from google import genai
from google.genai import types
from json_repair import repair_json

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 16384

DAILY_RECAP_PROMPT = """You are a productivity assistant. Given a list of calendar events and meeting summaries for a specific day, generate a comprehensive daily recap.

Rules:
1. Summarize the key activities, decisions, and outcomes of the day.
2. Highlight action items and follow-ups.
3. Note any blockers or risks mentioned.
4. Group related items together logically.
5. Use the same language as the summaries.
6. Be concise but thorough.

You MUST respond with a valid JSON object:
{
  "title": "Short recap title for the day (max 8 words)",
  "highlights": ["Key highlight 1", "Key highlight 2"],
  "recap": "Full markdown recap of the day",
  "action_items": ["Action item 1", "Action item 2"],
  "blockers": ["Blocker 1"]
}

Return ONLY the JSON object, no other text before or after it.
"""


class DailyRecapService:
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate_recap(self, date_str: str, events: list[dict], summaries: list[dict]) -> dict:
        """Generate a daily recap from events and summaries."""
        # Build context
        context_parts = [f"Date: {date_str}\n"]

        if events:
            context_parts.append("## Calendar Events\n")
            for ev in events:
                time_range = f"{ev.get('start_at', '?')} – {ev.get('end_at', '?')}"
                context_parts.append(f"- **{ev.get('title', 'Untitled')}** ({time_range})")
                if ev.get("description"):
                    context_parts.append(f"  {ev['description']}")
                if ev.get("location"):
                    context_parts.append(f"  Location: {ev['location']}")

        if summaries:
            context_parts.append("\n## Meeting Summaries\n")
            for s in summaries:
                context_parts.append(f"### {s.get('title', 'Untitled')}")
                if s.get("tags"):
                    context_parts.append(f"Tags: {', '.join(s['tags'])}")
                context_parts.append(s.get("summary", ""))
                context_parts.append("")

        user_content = "\n".join(context_parts)

        logger.info("Generating daily recap for %s with Gemini…", date_str)
        response = self._client.models.generate_content(
            model=self._model,
            config=types.GenerateContentConfig(
                system_instruction=DAILY_RECAP_PROMPT,
                response_mime_type="application/json",
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
            contents=user_content,
        )

        raw = response.text or ""
        return self._parse_response(raw)

    @staticmethod
    def _parse_response(raw: str) -> dict:
        default = {
            "title": "",
            "highlights": [],
            "recap": "",
            "action_items": [],
            "blockers": [],
        }

        # 1. Try strict JSON
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {**default, **data}
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. Repair JSON
        try:
            repaired = repair_json(raw, return_objects=True)
            if isinstance(repaired, dict):
                return {**default, **repaired}
        except Exception:
            pass

        # 3. Fallback
        return {**default, "recap": raw.strip()}
