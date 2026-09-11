import json

import graph.nodes.router as router_mod
from tests.unit.graph.nodes._helpers import FakeResponse, base_state


class TestRouterNode:
    def test_route_query_returns_intent_and_category_from_llm(self, monkeypatch):
        monkeypatch.setattr(
            router_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(json.dumps({"intent": "retrieve", "category": "ifrs"})),
        )
        assert router_mod.route_query("What is IFRS 16?") == ("retrieve", "ifrs")

    def test_route_query_ignores_category_when_intent_is_not_retrieve(self, monkeypatch):
        monkeypatch.setattr(
            router_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(json.dumps({"intent": "web_search", "category": "ifrs"})),
        )
        assert router_mod.route_query("What's the EUR/TND rate today?") == ("web_search", None)

    def test_route_query_falls_back_on_empty_response(self, monkeypatch):
        monkeypatch.setattr(router_mod, "getResponseFromLLM", lambda *a, **kw: FakeResponse(None))
        assert router_mod.route_query("hello") == ("general_knowledge", None)

    def test_route_query_falls_back_on_malformed_json(self, monkeypatch):
        monkeypatch.setattr(
            router_mod, "getResponseFromLLM", lambda *a, **kw: FakeResponse("not json")
        )
        assert router_mod.route_query("hello") == ("general_knowledge", None)

    def test_route_query_falls_back_on_missing_intent_key(self, monkeypatch):
        monkeypatch.setattr(
            router_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(json.dumps({"unexpected": "value"})),
        )
        assert router_mod.route_query("hello") == ("general_knowledge", None)

    def test_route_query_falls_back_on_unrecognized_intent(self, monkeypatch):
        monkeypatch.setattr(
            router_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(json.dumps({"intent": "do_a_barrel_roll"})),
        )
        assert router_mod.route_query("hello") == ("general_knowledge", None)

    def test_route_query_falls_back_on_llm_exception(self, monkeypatch):
        def _raise(*a, **kw):
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(router_mod, "getResponseFromLLM", _raise)
        assert router_mod.route_query("hello") == ("general_knowledge", None)

    def test_route_query_includes_history_in_the_prompt(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            router_mod,
            "getResponseFromLLM",
            lambda system_prompt, user_prompt, temp: (
                captured.update(user_prompt=user_prompt)
                or FakeResponse(json.dumps({"intent": "general_knowledge", "category": None}))
            ),
        )
        router_mod.route_query(
            "And what about last year?",
            history=[{"role": "user", "content": "What is the VAT rate?"}],
        )
        assert "What is the VAT rate?" in captured["user_prompt"]

    def test_router_node_wraps_intent_and_category_in_state_dict(self, monkeypatch):
        monkeypatch.setattr(
            router_mod, "route_query", lambda query, history=None: ("retrieve", "tax_code")
        )
        result = router_mod.router_node(base_state(query="Comment est calcule l'IS en Tunisie ?"))
        assert result == {"intent": "retrieve", "category": "tax_code"}
