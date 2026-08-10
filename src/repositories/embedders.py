import logging

import httpx
from google import genai

logger = logging.getLogger(__name__)


class GeminiEmbedder:
    """Embed text via the Google Gemini embedding API (cloud)."""

    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def id(self) -> str:
        return f"gemini:{self._model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._client.models.embed_content(
            model=self._model,
            contents=texts,
        )
        embeddings = result.embeddings or []
        return [e.values for e in embeddings if e.values is not None]


class LocalEmbedder:
    """Embed text locally with sentence-transformers (offline). Imported + loaded lazily."""

    def __init__(self, model_name: str, device: str = "auto"):
        self._model_name = model_name
        # SentenceTransformer wants None (not "auto") to auto-detect the device.
        self._device = None if device in (None, "", "auto") else device
        self._model = None  # lazy-loaded

    @property
    def id(self) -> str:
        return f"local:{self._model_name}"

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(
                "Loading embedding model '%s' (device=%s)…",
                self._model_name,
                self._device or "auto",
            )
            self._model = SentenceTransformer(self._model_name, device=self._device)
            logger.info(
                "Embedding model loaded (max_seq_length=%s).",
                self._model.max_seq_length,
            )
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        self._warn_if_truncated(model, texts)
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def _warn_if_truncated(self, model, texts: list[str]) -> None:
        """Warn when an input exceeds the model's context, since it will be silently truncated."""
        max_len = getattr(model, "max_seq_length", None)
        tokenizer = getattr(model, "tokenizer", None)
        if not max_len or tokenizer is None:
            return
        for i, text in enumerate(texts):
            try:
                n_tokens = len(tokenizer.encode(text))
            except Exception:
                continue
            if n_tokens > max_len:
                logger.warning(
                    "Embedding input #%d has %d tokens > model max_seq_length %d; it will be "
                    "truncated. Consider a longer-context LOCAL_EMBEDDING_MODEL.",
                    i,
                    n_tokens,
                    max_len,
                )


class OllamaEmbedder:
    """Embed via a shared Ollama server (OpenAI-compatible API) — one model for all web workers."""

    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def id(self) -> str:
        return f"ollama:{self._model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": texts, "options": {"num_batch": 8192}},
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("embeddings", [])
