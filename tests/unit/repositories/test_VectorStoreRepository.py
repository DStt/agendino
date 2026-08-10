from types import SimpleNamespace

from repositories.VectorStoreRepository import VectorStoreRepository, build_summary_document


class FakeEmbedder:
    def __init__(self, id_, dim=3):
        self._id = id_
        self._dim = dim

    @property
    def id(self):
        return self._id

    def embed(self, texts):
        return [[0.1] * self._dim for _ in texts]


class TestBuildSummaryDocument:
    def test_full(self):
        s = SimpleNamespace(id=7, recording_name="rec", title="T", tags="a,b", version=2, summary="body")
        doc, meta = build_summary_document(s)
        assert doc == "Title: T\nTags: a,b\n\nbody"
        assert meta == {"summary_id": 7, "recording_name": "rec", "title": "T", "tags": "a,b", "version": 2}

    def test_missing_title_and_tags(self):
        s = SimpleNamespace(id=1, recording_name="r", title=None, tags=None, version=1, summary="body")
        doc, meta = build_summary_document(s)
        assert doc == "\nbody"
        assert meta["title"] == "" and meta["tags"] == ""


class TestMismatchReset:
    def test_same_embedder_preserves_store(self, tmp_path):
        path = str(tmp_path / "vs")
        r1 = VectorStoreRepository(path, FakeEmbedder("local:A"))
        r1.add_summary(1, "doc text", {"summary_id": 1})
        assert r1.count() == 1
        r2 = VectorStoreRepository(path, FakeEmbedder("local:A"))
        assert r2.count() == 1  # same embedder id → store kept

    def test_changed_embedder_clears_store(self, tmp_path):
        path = str(tmp_path / "vs")
        r1 = VectorStoreRepository(path, FakeEmbedder("local:A", dim=3))
        r1.add_summary(1, "doc text", {"summary_id": 1})
        assert r1.count() == 1
        r2 = VectorStoreRepository(path, FakeEmbedder("ollama:B", dim=4))
        assert r2.count() == 0  # different embedder id → reset

    def test_search_empty_returns_list(self, tmp_path):
        r = VectorStoreRepository(str(tmp_path / "vs"), FakeEmbedder("local:A"))
        assert r.search("anything") == []
