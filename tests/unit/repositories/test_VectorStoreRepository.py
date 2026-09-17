import pytest

from repositories.VectorStoreRepository import VectorStoreRepository


class TestVectorStoreRepositoryOptionalClient:
    def test_missing_key_does_not_raise(self, tmp_path):
        repo = VectorStoreRepository(persist_path=str(tmp_path / "vs"), api_key="", model="m")
        assert repo.count() == 0

    def test_embed_without_key_raises(self, tmp_path):
        repo = VectorStoreRepository(persist_path=str(tmp_path / "vs"), api_key="", model="m")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            repo._embed(["hello"])
