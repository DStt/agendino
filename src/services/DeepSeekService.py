import logging
import time

import httpx

logger = logging.getLogger(__name__)

DEFAULT_DEEPSEEK_MODEL = "deepseek-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
# deepseek-flash / deepseek-v4-pro support up to 384K output tokens.
DEFAULT_DEEPSEEK_MAX_TOKENS = 32768
MAX_DEEPSEEK_TOKENS = 393216
# Transient statuses worth retrying with exponential backoff.
RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


class DeepSeekService:
    """Client for calling DeepSeek API (OpenAI-compatible chat completions)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
        timeout: float = 180.0,
        max_tokens: int = DEFAULT_DEEPSEEK_MAX_TOKENS,
        thinking: str | None = None,
    ):
        self._api_key = api_key
        self._model = model or DEFAULT_DEEPSEEK_MODEL
        self._base_url = (base_url or DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._max_tokens = max_tokens or DEFAULT_DEEPSEEK_MAX_TOKENS
        self._thinking = thinking if thinking in ("enabled", "disabled") else None

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    @property
    def model(self) -> str:
        return self._model

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def thinking(self) -> str | None:
        return self._thinking

    def generate_chat(
        self,
        user_content: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> tuple[str, bool]:
        """Call DeepSeek chat completions API.

        Args:
            user_content: The user message / prompt.
            system_prompt: Optional system instruction.
            json_mode: If True, request JSON object output format.
            max_tokens: Maximum tokens to generate. When thinking mode is enabled
                this budget also covers the hidden reasoning tokens, which is why
                the default is generous. Defaults to the service-level value and is
                clamped to the API maximum (393216).

        Returns:
            Tuple of (response_text, is_truncated).
        """
        if not self.is_configured:
            raise ValueError("DeepSeek API key is not configured (set DEEPSEEK_API_KEY)")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})

        requested = self._max_tokens if max_tokens is None else max_tokens
        effective_max_tokens = max(1, min(int(requested), MAX_DEEPSEEK_TOKENS))

        payload: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": effective_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self._thinking:
            payload["thinking"] = {"type": self._thinking}

        url = f"{self._base_url}/chat/completions"
        logger.info(
            "Calling DeepSeek API (model=%s, url=%s, json_mode=%s, max_tokens=%s, thinking=%s)…",
            self._model,
            url,
            json_mode,
            effective_max_tokens,
            self._thinking or "default",
        )

        data = self._post_with_retries(url, headers, payload)

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("DeepSeek returned an empty choices list")

        choice = choices[0]
        content = choice.get("message", {}).get("content", "")
        finish_reason = choice.get("finish_reason")
        is_truncated = finish_reason == "length"

        if is_truncated:
            logger.warning("DeepSeek response was truncated (finish_reason=length)")

        return content, is_truncated

    def _post_with_retries(
        self,
        url: str,
        headers: dict,
        payload: dict,
        attempts: int = 3,
        base_delay: float = 0.75,
    ) -> dict:
        """POST with exponential backoff for transient failures."""
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if hasattr(e, "response") else 0
                error_body = e.response.text if hasattr(e, "response") else str(e)
                if status in RETRYABLE_STATUS_CODES and attempt < attempts:
                    logger.warning("DeepSeek API %s (attempt %d/%d); retrying", status, attempt, attempts)
                    time.sleep(base_delay * (2 ** (attempt - 1)))
                    last_error = e
                    continue
                logger.error("DeepSeek API HTTP error %s: %s", status, error_body)
                status_label = status if status else "unknown"
                raise RuntimeError(f"DeepSeek API error ({status_label}): {error_body}") from e
            except (httpx.TimeoutException, httpx.TransportError) as e:
                if attempt < attempts:
                    logger.warning("DeepSeek request failed (attempt %d/%d): %s; retrying", attempt, attempts, e)
                    time.sleep(base_delay * (2 ** (attempt - 1)))
                    last_error = e
                    continue
                logger.error("DeepSeek request failed: %s", e)
                raise
            except Exception as e:
                logger.error("DeepSeek request failed: %s", e)
                raise

        raise RuntimeError(f"DeepSeek request failed after {attempts} attempts: {last_error}")
