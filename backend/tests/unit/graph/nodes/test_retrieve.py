import graph.nodes.retrieve as retrieve_mod
from tests.unit.graph.nodes._helpers import base_state


class TestRetrieveNode:
    def test_retrieve_context_joins_documents_with_blank_line(self, monkeypatch):
        monkeypatch.setattr(
            retrieve_mod.ollama, "embed", lambda **kw: {"embeddings": [[0.1, 0.2, 0.3]]}
        )

        class _Collection:
            def query(self, **kwargs):
                return {"documents": [["Chunk one.", "Chunk two."]]}

        monkeypatch.setattr(retrieve_mod, "collection", _Collection())
        result = retrieve_mod.retrieve_context("What is IFRS 16?", "ifrs", n_results=5)
        assert result == "Chunk one.\n\nChunk two."

    def test_queries_with_category_filter_and_n_results(self, monkeypatch):
        monkeypatch.setattr(
            retrieve_mod.ollama, "embed", lambda **kw: {"embeddings": [[0.1, 0.2, 0.3]]}
        )
        captured = {}

        class _Collection:
            def query(self, **kwargs):
                captured.update(kwargs)
                return {"documents": [["chunk"]]}

        monkeypatch.setattr(retrieve_mod, "collection", _Collection())
        retrieve_mod.retrieve_context("query", "tax_code", n_results=3)

        assert captured["where"] == {"category": {"$eq": "tax_code"}}
        assert captured["n_results"] == 3
        assert captured["query_embeddings"] == [[0.1, 0.2, 0.3]]

    def test_uses_embeddinggemma_model(self, monkeypatch):
        captured = {}

        def _fake_embed(**kwargs):
            captured.update(kwargs)
            return {"embeddings": [[0.1]]}

        monkeypatch.setattr(retrieve_mod.ollama, "embed", _fake_embed)

        class _Collection:
            def query(self, **kwargs):
                return {"documents": [["chunk"]]}

        monkeypatch.setattr(retrieve_mod, "collection", _Collection())
        retrieve_mod.retrieve_context("some query", "ifrs")

        assert captured == {"model": "embeddinggemma", "input": "some query"}

    def test_returns_fallback_message_when_no_documents(self, monkeypatch):
        monkeypatch.setattr(
            retrieve_mod.ollama, "embed", lambda **kw: {"embeddings": [[0.1, 0.2, 0.3]]}
        )

        class _Collection:
            def query(self, **kwargs):
                return {"documents": [[]]}

        monkeypatch.setattr(retrieve_mod, "collection", _Collection())
        assert (
            retrieve_mod.retrieve_context("obscure query", "tax_code")
            == "No local documents found."
        )

    def test_returns_fallback_message_when_documents_key_missing(self, monkeypatch):
        monkeypatch.setattr(
            retrieve_mod.ollama, "embed", lambda **kw: {"embeddings": [[0.1, 0.2, 0.3]]}
        )

        class _Collection:
            def query(self, **kwargs):
                return {}

        monkeypatch.setattr(retrieve_mod, "collection", _Collection())
        assert retrieve_mod.retrieve_context("query", "ifrs") == "No local documents found."

    def test_retrieval_node_wraps_context_and_increments_attempts(self, monkeypatch):
        monkeypatch.setattr(
            retrieve_mod, "retrieve_context", lambda q, c, n: "Some retrieved context."
        )
        result = retrieve_mod.retrieval_node(base_state(search_query="q", category="ifrs"))
        assert result == {"context": "Some retrieved context.", "retrieval_attempts": 1}

    def test_retrieval_node_increments_from_existing_attempts(self, monkeypatch):
        monkeypatch.setattr(retrieve_mod, "retrieve_context", lambda q, c, n: "context")
        result = retrieve_mod.retrieval_node(
            base_state(search_query="q", category="ifrs", retrieval_attempts=2)
        )
        assert result["retrieval_attempts"] == 3

    def test_retrieval_node_passes_search_query_category_and_default_n_results(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            retrieve_mod,
            "retrieve_context",
            lambda q, c, n: captured.update(query=q, category=c, n_results=n) or "context",
        )
        retrieve_mod.retrieval_node(
            base_state(query="original", search_query="refined question", category="tax_code")
        )
        assert captured == {"query": "refined question", "category": "tax_code", "n_results": 5}

    def test_retrieval_node_falls_back_to_raw_query_when_search_query_missing(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            retrieve_mod,
            "retrieve_context",
            lambda q, c, n: captured.update(query=q) or "context",
        )
        state = base_state(query="original question", category="tax_code")
        state.pop("search_query")
        retrieve_mod.retrieval_node(state)
        assert captured["query"] == "original question"
