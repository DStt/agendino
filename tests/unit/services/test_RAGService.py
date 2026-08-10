from unittest.mock import MagicMock

from services.RAGService import (
    RAG_DOC_CHAR_CAP,
    OllamaRAGService,
    build_mind_map_content,
    build_rag_context,
    parse_branch_json,
    parse_mind_map_json,
)


class TestBuildRagContext:
    def test_caps_long_docs(self):
        long = "x" * (RAG_DOC_CHAR_CAP + 500)
        ctx, sources = build_rag_context([{"metadata": {"title": "A"}, "document": long}])
        assert "…[truncated]" in ctx
        assert len(ctx) < len(long)
        assert sources[0]["title"] == "A"

    def test_short_docs_not_capped(self):
        ctx, _ = build_rag_context([{"metadata": {"title": "A"}, "document": "short"}])
        assert "…[truncated]" not in ctx

    def test_sources_and_separator(self):
        docs = [
            {"metadata": {"title": "T1", "recording_name": "r1", "summary_id": 5}, "document": "a", "distance": 0.1},
            {"document": "b"},
        ]
        ctx, sources = build_rag_context(docs)
        assert "[T1]\na" in ctx and "[Source 2]\nb" in ctx
        assert "\n\n---\n\n" in ctx
        assert sources[0]["summary_id"] == 5
        assert sources[1]["title"] == "Source 2"


class TestBuildMindMapContent:
    def test_truncates_summary_to_600(self):
        content = build_mind_map_content([{"id": 1, "title": "T", "tags": ["a", "b"], "summary": "x" * 900}])
        assert "[ID: 1] Title: T" in content
        assert "Tags: a, b" in content
        assert content.count("x") == 600


class TestParsing:
    def test_mind_map_valid(self):
        assert parse_mind_map_json('{"central_topic":"Z","branches":[]}')["central_topic"] == "Z"

    def test_mind_map_fallback(self):
        fb = parse_mind_map_json("not json at all")
        assert fb["central_topic"] == "Knowledge Base"
        assert fb["branches"] == []

    def test_branch_valid(self):
        b = parse_branch_json('{"label":"X","children":[{"label":"k","summary_ids":[1]}]}')
        assert b["label"] == "X"
        assert b["children"][0]["summary_ids"] == [1]

    def test_branch_fallback(self):
        assert parse_branch_json("garbage") == {"label": "Theme", "children": []}

    def test_branch_repaired_when_malformed(self):
        # missing closing brace/bracket — json_repair should salvage it
        assert parse_branch_json('{"label":"X","children":[]')["label"] == "X"


class TestOllamaRAGService:
    def test_base_url_trailing_slash_stripped(self):
        assert OllamaRAGService("http://x:11434/", "m")._base_url == "http://x:11434"

    def test_ask(self):
        svc = OllamaRAGService("http://o:11434", "m")
        svc._chat = MagicMock(return_value="the answer")
        res = svc.ask("q?", [{"metadata": {"title": "T"}, "document": "ctx"}])
        assert res["answer"] == "the answer"
        assert res["sources"][0]["title"] == "T"

    def test_generate_mind_map(self):
        svc = OllamaRAGService("http://o:11434", "m")
        svc._chat = MagicMock(return_value='{"central_topic":"C","branches":[],"connections":[]}')
        assert svc.generate_mind_map([{"id": 1, "summary": "s"}])["central_topic"] == "C"

    def test_label_cluster(self):
        svc = OllamaRAGService("http://o:11434", "m")
        svc._chat = MagicMock(return_value='{"label":"L","children":[{"label":"k","summary_ids":[2]}]}')
        b = svc.label_cluster([{"id": 2, "summary": "s"}])
        assert b["label"] == "L"
        assert b["children"][0]["summary_ids"] == [2]

    def test_chat_posts_to_openai_endpoint(self, monkeypatch):
        captured = {}

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "hi"}}]}

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return Resp()

        import services.RAGService as mod
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        out = OllamaRAGService("http://x:11434", "m")._chat([{"role": "user", "content": "q"}], json_mode=True)
        assert out == "hi"
        assert captured["url"] == "http://x:11434/v1/chat/completions"
        assert captured["json"]["response_format"] == {"type": "json_object"}
