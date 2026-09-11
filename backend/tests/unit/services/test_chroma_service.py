import importlib
from unittest.mock import MagicMock

import chromadb

import services.chroma_service as chroma_service_mod


class TestChromaService:
    def test_constructs_persistent_client_with_expected_path(self, monkeypatch):
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.get_collection.return_value = "the-collection"
        monkeypatch.setattr(chromadb, "PersistentClient", mock_client_cls)

        reloaded = importlib.reload(chroma_service_mod)

        mock_client_cls.assert_called_once_with(path="knowledge_base/chroma_db")
        assert reloaded.collection == "the-collection"

    def test_fetches_expected_collection_name(self, monkeypatch):
        mock_client_cls = MagicMock()
        monkeypatch.setattr(chromadb, "PersistentClient", mock_client_cls)

        reloaded = importlib.reload(chroma_service_mod)

        reloaded.client.get_collection.assert_called_once_with(name="ai_assistant")

    def test_propagates_error_when_collection_missing(self, monkeypatch):
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.get_collection.side_effect = ValueError(
            "Collection [ai_assistant] does not exist"
        )
        monkeypatch.setattr(chromadb, "PersistentClient", mock_client_cls)

        try:
            importlib.reload(chroma_service_mod)
            assert False, "expected reload to raise ValueError"
        except ValueError as exc:
            assert "does not exist" in str(exc)
