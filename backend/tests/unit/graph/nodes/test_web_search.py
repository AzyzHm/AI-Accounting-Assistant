import graph.nodes.web_search as web_search_mod
from tests.unit.graph.nodes._helpers import base_state


class TestWebSearchNode:
    def test_returns_context_from_search_service(self, monkeypatch):
        monkeypatch.setattr(
            web_search_mod,
            "search_web",
            lambda query: "Source: example.com\nContent: EUR/TND rate today.",
        )
        result = web_search_mod.web_search_node(
            base_state(query="current EUR/TND exchange rate", search_query="EUR/TND rate today")
        )
        assert result == {"context": "Source: example.com\nContent: EUR/TND rate today."}

    def test_passes_search_query_through_unchanged(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            web_search_mod,
            "search_web",
            lambda query: captured.setdefault("query", query) and "",
        )
        web_search_mod.web_search_node(
            base_state(query="some question", search_query="refined question")
        )
        assert captured["query"] == "refined question"

    def test_falls_back_to_raw_query_when_search_query_missing(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            web_search_mod,
            "search_web",
            lambda query: captured.setdefault("query", query) and "",
        )
        state = base_state(query="some question")
        state.pop("search_query")
        web_search_mod.web_search_node(state)
        assert captured["query"] == "some question"

    def test_ignores_other_state_fields(self, monkeypatch):
        monkeypatch.setattr(web_search_mod, "search_web", lambda query: "context text")
        state = base_state(category="tax_code", answer="stale", is_valid=False)
        assert web_search_mod.web_search_node(state) == {"context": "context text"}
