from unittest.mock import MagicMock

import pytest

from controllers import RAGController as rc
from controllers.RAGController import RAGController


# ── module-level helpers ──

class TestKmeans:
    def test_separates_two_groups(self):
        g1 = [[10.0, 0.0], [11.0, 0.1], [10.5, -0.1], [9.8, 0.2]]
        g2 = [[-10.0, 0.0], [-11.0, 0.2], [-9.5, 0.1], [-10.2, -0.2]]
        labels, centroids = rc._kmeans(g1 + g2, 2, seed=1)
        assert len(centroids) == 2
        assert len(set(labels[:4])) == 1 and len(set(labels[4:])) == 1
        assert labels[0] != labels[4]


class TestCentralTopic:
    def test_most_common_tag(self):
        assert rc._central_topic([{"tags": ["x", "y"]}, {"tags": ["x"]}]) == "x"

    def test_default_when_no_tags(self):
        assert rc._central_topic([{"tags": []}]) == "Knowledge Base"


class TestConnections:
    def test_links_similar_centroids(self):
        br = [{"id": "branch_1"}, {"id": "branch_2"}]
        conns = rc._connections([[1.0, 0.0], [0.99, 0.02]], br)  # near-identical → linked
        assert conns and conns[0]["from"] == "branch_1" and conns[0]["to"] == "branch_2"

    def test_no_links_for_dissimilar(self):
        br = [{"id": "branch_1"}, {"id": "branch_2"}]
        assert rc._connections([[1.0, 0.0], [-1.0, 0.0]], br) == []  # opposite → below threshold

    def test_empty_for_single_branch(self):
        assert rc._connections([[1.0, 0.0]], [{"id": "branch_1"}]) == []


# ── generate_mind_map / get_stats / search ──

def _vs_with(records):
    vs = MagicMock()
    vs.get_all.return_value = {
        "ids": [f"summary_{r['id']}" for r in records],
        "documents": [r["summary"] for r in records],
        "metadatas": [{"summary_id": r["id"], "title": r.get("title", ""), "tags": ",".join(r.get("tags", []))}
                      for r in records],
        "embeddings": [r["embedding"] for r in records],
    }
    return vs


def _records(n):
    centers = [[50.0, 0.0], [-50.0, 0.0], [0.0, 50.0]]  # 3 well-separated groups (>= k)
    recs = []
    for i in range(n):
        c = centers[i % 3]
        recs.append({"id": i + 1, "title": f"t{i}", "tags": ["alpha"], "summary": f"s{i}",
                     "embedding": [c[0] + i * 0.01, c[1] + i * 0.01]})
    return recs


@pytest.fixture
def controller_factory(tmp_path):
    def _make(vs, rag_service=None):
        return RAGController(MagicMock(), vs, rag_service or MagicMock(), str(tmp_path))
    return _make


class FakeRAG:
    def label_cluster(self, members):
        return {"label": "Theme", "children": [{"label": "ins", "summary_ids": [m["id"] for m in members]}]}

    def generate_mind_map(self, summaries):
        return {"central_topic": "Single", "branches": [], "connections": []}


class TestGenerateMindMap:
    def test_clusters_above_threshold(self, controller_factory):
        ctrl = controller_factory(_vs_with(_records(20)), FakeRAG())
        res = ctrl.generate_mind_map()
        assert res["ok"] and res["summary_count"] == 20
        mm = res["mind_map"]
        assert mm["central_topic"] == "alpha"
        assert len(mm["branches"]) >= 2
        assert all(b["id"].startswith("branch_") for b in mm["branches"])
        assert all(c["id"].startswith("leaf_") for b in mm["branches"] for c in b["children"])

    def test_single_shot_fallback_below_threshold(self, controller_factory):
        ctrl = controller_factory(_vs_with(_records(5)), FakeRAG())
        res = ctrl.generate_mind_map()
        assert res["ok"] and res["mind_map"]["central_topic"] == "Single"

    def test_empty_store_returns_error(self, controller_factory):
        vs = MagicMock()
        vs.get_all.return_value = {"ids": []}
        res = controller_factory(vs).generate_mind_map()
        assert res["ok"] is False and "Load summaries" in res["error"]

    def test_summary_ids_filter(self, controller_factory):
        ctrl = controller_factory(_vs_with(_records(20)), FakeRAG())
        res = ctrl.generate_mind_map(summary_ids=[1, 2, 3])
        assert res["ok"] and res["summary_count"] == 3  # filtered → below threshold, single-shot


class TestGetStats:
    def test_needs_reload_true_when_loaded_empty(self, controller_factory):
        vs = MagicMock()
        vs.count.return_value = 0
        ctrl = controller_factory(vs)
        ctrl._sqlite_db_repository.get_latest_summaries_map.return_value = {"a": object(), "b": object()}
        stats = ctrl.get_stats()
        assert stats["total_summaries"] == 2 and stats["loaded_count"] == 0
        assert stats["needs_reload"] is True

    def test_needs_reload_false_when_loaded(self, controller_factory):
        vs = MagicMock()
        vs.count.return_value = 2
        ctrl = controller_factory(vs)
        ctrl._sqlite_db_repository.get_latest_summaries_map.return_value = {"a": object(), "b": object()}
        assert ctrl.get_stats()["needs_reload"] is False


class TestSearch:
    def test_error_returns_json_not_raise(self, controller_factory):
        vs = MagicMock()
        vs.count.return_value = 1
        vs.search.side_effect = RuntimeError("boom")
        res = controller_factory(vs).search("q")
        assert res["ok"] is False and "boom" in res["error"]

    def test_empty_store_message(self, controller_factory):
        vs = MagicMock()
        vs.count.return_value = 0
        res = controller_factory(vs).search("q")
        assert res["ok"] is False and "Load summaries" in res["error"]
