from unittest.mock import MagicMock

from repositories.embedders import GeminiEmbedder, LocalEmbedder, OllamaEmbedder


class TestOllamaEmbedder:
    def test_id(self):
        assert OllamaEmbedder("http://x", "bge-m3").id == "ollama:bge-m3"

    def test_base_url_trailing_slash_stripped(self):
        assert OllamaEmbedder("http://x:11434/", "m")._base_url == "http://x:11434"

    def test_embed_uses_native_api_with_num_batch(self, monkeypatch):
        captured = {}

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return Resp()

        import repositories.embedders as mod
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        out = OllamaEmbedder("http://ollama:11434", "bge-m3").embed(["a", "b"])
        assert out == [[0.1, 0.2], [0.3, 0.4]]
        assert captured["url"] == "http://ollama:11434/api/embed"          # native endpoint, not /v1/embeddings
        assert captured["json"]["input"] == ["a", "b"]
        assert captured["json"]["options"]["num_batch"] == 8192            # so long summaries fit one batch


class TestLocalEmbedder:
    def test_id(self):
        assert LocalEmbedder("BAAI/bge-m3").id == "local:BAAI/bge-m3"

    def test_auto_device_maps_to_none(self):
        assert LocalEmbedder("m", "auto")._device is None
        assert LocalEmbedder("m", "")._device is None

    def test_explicit_device_kept(self):
        assert LocalEmbedder("m", "cuda")._device == "cuda"


class TestGeminiEmbedder:
    def test_id(self, monkeypatch):
        monkeypatch.setattr("google.genai.Client", lambda api_key=None: MagicMock())
        assert GeminiEmbedder("fake-key", "gemini-embedding-001").id == "gemini:gemini-embedding-001"

    def test_embed_extracts_values(self, monkeypatch):
        monkeypatch.setattr("google.genai.Client", lambda api_key=None: MagicMock())
        emb = GeminiEmbedder("fake-key", "model")
        result = MagicMock()
        value = MagicMock()
        value.values = [0.1, 0.2]
        result.embeddings = [value]
        emb._client = MagicMock()
        emb._client.models.embed_content.return_value = result
        assert emb.embed(["x"]) == [[0.1, 0.2]]
