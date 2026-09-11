import json

import graph.nodes.validate as validate_mod
from tests.unit.graph.nodes._helpers import FakeResponse, base_state


class TestValidateNode:
    def test_skips_llm_for_general_knowledge(self, monkeypatch):
        called = {}

        def _fail_if_called(*a, **kw):
            called["yes"] = True

        monkeypatch.setattr(validate_mod, "getResponseFromLLM", _fail_if_called)
        result = validate_mod.validate_node(base_state(intent="general_knowledge"))
        assert result == {"is_valid": True}
        assert "yes" not in called

    def test_returns_true_for_valid_context(self, monkeypatch):
        monkeypatch.setattr(
            validate_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(json.dumps({"is_valid": True, "optimized_query": None})),
        )
        state = base_state(context="IFRS 16 covers lease accounting.")
        assert validate_mod.validate_node(state) == {"is_valid": True}

    def test_returns_false_and_optimized_query_for_invalid_context(self, monkeypatch):
        monkeypatch.setattr(
            validate_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(
                json.dumps({"is_valid": False, "optimized_query": "IFRS 16 lease term definition"})
            ),
        )
        state = base_state(context="unrelated text")
        assert validate_mod.validate_node(state) == {
            "is_valid": False,
            "search_query": "IFRS 16 lease term definition",
        }

    def test_returns_false_without_search_query_when_no_optimized_query_given(self, monkeypatch):
        monkeypatch.setattr(
            validate_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(json.dumps({"is_valid": False, "optimized_query": None})),
        )
        state = base_state(context="unrelated text")
        assert validate_mod.validate_node(state) == {"is_valid": False}

    def test_defaults_to_false_on_malformed_json(self, monkeypatch):
        monkeypatch.setattr(
            validate_mod, "getResponseFromLLM", lambda *a, **kw: FakeResponse("not json")
        )
        assert validate_mod.validate_node(base_state(context="c")) == {"is_valid": False}

    def test_defaults_to_false_on_empty_response(self, monkeypatch):
        monkeypatch.setattr(validate_mod, "getResponseFromLLM", lambda *a, **kw: FakeResponse(None))
        assert validate_mod.validate_node(base_state(context="c")) == {"is_valid": False}

    def test_defaults_to_false_on_llm_exception(self, monkeypatch):
        def _raise(*a, **kw):
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(validate_mod, "getResponseFromLLM", _raise)
        assert validate_mod.validate_node(base_state(context="c")) == {"is_valid": False}
