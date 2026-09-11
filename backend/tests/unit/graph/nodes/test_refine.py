import json

import graph.nodes.refine as refine_mod
from tests.unit.graph.nodes._helpers import FakeResponse, base_state


class TestRefineNode:
    def test_refine_query_returns_refined_text(self, monkeypatch):
        monkeypatch.setattr(
            refine_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(json.dumps({"refined_query": "Who issues IFRS 16?"})),
        )
        assert refine_mod.refine_query("who was it?") == "Who issues IFRS 16?"

    def test_refine_query_falls_back_to_original_on_empty_response(self, monkeypatch):
        monkeypatch.setattr(refine_mod, "getResponseFromLLM", lambda *a, **kw: FakeResponse(None))
        assert refine_mod.refine_query("what is IFRS 16?") == "what is IFRS 16?"

    def test_refine_query_falls_back_to_original_on_malformed_json(self, monkeypatch):
        monkeypatch.setattr(
            refine_mod, "getResponseFromLLM", lambda *a, **kw: FakeResponse("not json")
        )
        assert refine_mod.refine_query("what is IFRS 16?") == "what is IFRS 16?"

    def test_refine_query_falls_back_to_original_on_missing_key(self, monkeypatch):
        monkeypatch.setattr(
            refine_mod,
            "getResponseFromLLM",
            lambda *a, **kw: FakeResponse(json.dumps({"unexpected": "value"})),
        )
        assert refine_mod.refine_query("what is IFRS 16?") == "what is IFRS 16?"

    def test_refine_query_falls_back_to_original_on_llm_exception(self, monkeypatch):
        def _raise(*a, **kw):
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(refine_mod, "getResponseFromLLM", _raise)
        assert refine_mod.refine_query("what is IFRS 16?") == "what is IFRS 16?"

    def test_refine_query_includes_history_in_the_prompt(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            refine_mod,
            "getResponseFromLLM",
            lambda system_prompt, user_prompt, temp: (
                captured.update(user_prompt=user_prompt)
                or FakeResponse(json.dumps({"refined_query": "resolved"}))
            ),
        )
        refine_mod.refine_query(
            "who was it?",
            history=[{"role": "assistant", "content": "IFRS 16 is issued by the IASB."}],
        )
        assert "IFRS 16 is issued by the IASB." in captured["user_prompt"]

    def test_refine_node_wraps_search_query_in_state_dict(self, monkeypatch):
        monkeypatch.setattr(refine_mod, "refine_query", lambda query, history=None: "clean query")
        result = refine_mod.refine_node(base_state(query="what is that?"))
        assert result == {"search_query": "clean query"}
