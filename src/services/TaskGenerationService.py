import os
import json
import logging
from google import genai
from google.genai import types

from json_repair import repair_json

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 8192

TASK_GENERATION_PROMPT = """You are a project management assistant. Given a meeting summary, generate actionable tasks that could be added to a Jira board.

Rules:
1. Each task must have a clear, concise **title** (suitable as a Jira ticket title).
2. Each task must have a **description** explaining what needs to be done.
3. If a task is too broad or large in scope, break it into **subtasks** — each subtask also has a title and description.
4. Focus on concrete, actionable items — NOT vague goals.
5. Use the same language as the summary.

You MUST respond with a valid JSON array of task objects:
[
  {
    "title": "Task title",
    "description": "What needs to be done",
    "subtasks": [
      {
        "title": "Subtask title",
        "description": "Subtask details"
      }
    ]
  }
]

If a task does not need subtasks, omit the "subtasks" field or set it to an empty array.
Return ONLY the JSON array, no other text before or after it.
"""


class TaskGenerationService:
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate_tasks(self, summary_text: str, summary_title: str | None = None) -> list[dict]:
        """Generate actionable tasks from a meeting summary using Gemini AI."""
        user_content = ""
        if summary_title:
            user_content += f"Meeting title: {summary_title}\n\n"
        user_content += f"Summary:\n{summary_text}"

        logger.info("Generating tasks from summary with Gemini…")
        response = self._client.models.generate_content(
            model=self._model,
            config=types.GenerateContentConfig(
                system_instruction=TASK_GENERATION_PROMPT,
                response_mime_type="application/json",
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
            contents=user_content,
        )

        raw = response.text or ""
        return self._parse_response(raw)

    @staticmethod
    def _parse_response(raw: str) -> list[dict]:
        """Parse the JSON response from Gemini into a list of task dicts."""

        def _validate_tasks(data: list) -> list[dict]:
            tasks = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                title = item.get("title", "").strip()
                if not title:
                    continue
                task = {
                    "title": title,
                    "description": item.get("description", "").strip(),
                    "subtasks": [],
                }
                for sub in item.get("subtasks", []) or []:
                    if isinstance(sub, dict) and sub.get("title", "").strip():
                        task["subtasks"].append(
                            {
                                "title": sub["title"].strip(),
                                "description": sub.get("description", "").strip(),
                            }
                        )
                tasks.append(task)
            return tasks

        # 1. Try strict JSON parse
        try:
            data = json.loads(raw)
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, list):
                return _validate_tasks(data)
            if isinstance(data, dict) and "tasks" in data:
                return _validate_tasks(data["tasks"])
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

        # 2. Fallback: repair JSON
        logger.warning("Strict JSON parse failed for tasks, attempting repair…")
        try:
            repaired = repair_json(raw, return_objects=True)
            if isinstance(repaired, str):
                repaired = json.loads(repaired)
            if isinstance(repaired, list):
                logger.info("JSON repair succeeded for tasks")
                return _validate_tasks(repaired)
            if isinstance(repaired, dict) and "tasks" in repaired:
                return _validate_tasks(repaired["tasks"])
        except Exception as e:
            logger.warning("JSON repair also failed for tasks: %s", e)

        # 3. Last resort: return empty
        logger.warning("All JSON parsing failed for tasks, returning empty list")
        return []
